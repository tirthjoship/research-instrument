"""Orchestrate the macro-beta scrubber: prices -> returns -> estimate -> aggregate.

Network-free by injection (price_provider + estimator). Reuses the same
price_provider closure as _build_weekly_brief so the brief and the scrubber see
identical price data.
"""

from __future__ import annotations

import math
from collections import Counter
from datetime import datetime, timedelta
from typing import Any, Callable

from loguru import logger

from application.macro_history_store import load_systematic_share_history
from domain.macro_beta import (
    aggregate_macro_exposure,
    align_returns,
    aligned_return_matrix,
    book_return_series,
    daily_returns,
)
from domain.models import BookMacroExposure, HoldingMacroExposure, MacroFactorBeta
from domain.risk_stats import adjusted_r2
from domain.risk_stats import diversification_ratio as _diversification_ratio
from domain.risk_stats import effective_number_of_bets, risk_contributions, vif_from_r2

PriceProvider = Callable[[str, datetime, datetime], "list[tuple[datetime, float]]"]

STANDARD_GICS_SECTORS: tuple[str, ...] = (
    "Information Technology",
    "Health Care",
    "Financials",
    "Consumer Discretionary",
    "Communication Services",
    "Industrials",
    "Consumer Staples",
    "Energy",
    "Utilities",
    "Real Estate",
    "Materials",
)


def _label_principal_components(
    loadings: list[list[str]],
    sector_fn: Callable[[str], str],
) -> tuple[tuple[str, ...], bool]:
    """Label each PC by dominant sector, or fall back to 'Bet N' + data_gap=True.

    A sector label is assigned ONLY when one sector covers >= 60% of the named
    (non-'Unknown') top loaders. 'Unknown' is a data-gap — excluded from dominance
    calculation. No narrative names are fabricated.
    """
    labels: list[str] = []
    data_gap = False
    used: dict[str, int] = {}
    for i, top_tickers in enumerate(loadings):
        named_sectors = [sector_fn(t) for t in top_tickers if sector_fn(t) != "Unknown"]
        if named_sectors:
            counts = Counter(named_sectors)
            top_sector, top_count = counts.most_common(1)[0]
            if top_count / len(named_sectors) >= 0.60:
                # Disambiguate a second/third PC dominated by the same sector:
                # it is a within-sector dispersion axis, not the same bet twice.
                used[top_sector] = used.get(top_sector, 0) + 1
                label = (
                    top_sector
                    if used[top_sector] == 1
                    else f"{top_sector} (within-sector spread)"
                )
                labels.append(label)
                continue
        labels.append(f"Bet {i + 1}")
        data_gap = True
    return (tuple(labels), data_gap)


def _sector_breakdown(
    holdings: list[Any],
    weights: dict[str, float],
    sector_fn: Callable[[str], str],
) -> tuple[
    dict[str, float],
    float,
    tuple[str, ...],
    tuple[dict[str, object], ...],
]:
    """Compute sector_weights, sector_hhi, sector_gaps, and holdings_meta.

    sector_hhi is computed over known (non-'Unknown') sectors only, to avoid
    overstating concentration when sector data is unavailable.
    """
    sector_weights: dict[str, float] = {}
    for h in holdings:
        w = weights.get(h.ticker, 0.0)
        if w == 0.0:
            continue
        s = sector_fn(h.ticker)
        sector_weights[s] = sector_weights.get(s, 0.0) + w

    # HHI only over known sectors
    hhi = sum(w * w for s, w in sector_weights.items() if s != "Unknown")

    sector_gaps = tuple(
        s
        for s in STANDARD_GICS_SECTORS
        if s not in sector_weights or sector_weights.get(s, 0.0) == 0.0
    )

    holdings_meta = tuple(
        {
            "ticker": h.ticker,
            "name": getattr(h, "name", h.ticker),
            "sector": sector_fn(h.ticker),
            "weight": weights.get(h.ticker, 0.0),
        }
        for h in holdings
        if h.ticker in weights
    )

    return (sector_weights, hhi, sector_gaps, holdings_meta)


def _suppressed_from_ci(
    beta_ci_by_factor: dict[str, tuple[float, float]],
) -> tuple[str, ...]:
    """Return factors whose beta CI straddles zero (lo < 0 < hi). NOT VIF-based."""
    return tuple(f for f, (lo, hi) in beta_ci_by_factor.items() if lo < 0.0 < hi)


class MacroBetaUseCase:
    def __init__(
        self,
        price_provider: PriceProvider,
        estimator: Any,  # MacroBetaEstimatorPort
        factors: list[str],
        alpha: float,
        headline_window: int,
        drift_window: int,
        thresholds: dict[str, float],
        history_days: int = 400,
        risk_analyzer: Any = None,
        sector_provider: Any = None,
        history_path: str | None = None,
    ) -> None:
        self._prices = price_provider
        self._est = estimator
        self._factors = factors
        self._alpha = alpha
        self._headline = headline_window
        self._drift = drift_window
        self._thresholds = thresholds
        self._history_days = history_days
        self._risk = risk_analyzer
        self._sector = sector_provider
        self._history_path = history_path

    def execute(self, holdings: list[Any], as_of: datetime) -> BookMacroExposure | None:
        start = as_of - timedelta(days=self._history_days)

        factor_rets: dict[str, list[tuple[datetime, float]]] = {}
        for f in self._factors:
            series = self._prices(f, start, as_of)
            rets = daily_returns(series)
            if len(rets) >= self._headline:
                factor_rets[f] = rets
            else:
                logger.warning(f"macro-beta: factor {f} dropped (insufficient history)")
        if not factor_rets:
            logger.warning("macro-beta: no usable factors — abstaining")
            return None
        factors = tuple(factor_rets)

        holding_rets: dict[str, list[tuple[datetime, float]]] = {}
        values: dict[str, float] = {}
        per_holding: list[HoldingMacroExposure] = []
        covered_value = 0.0
        total_value = 0.0

        for h in holdings:
            series = self._prices(h.ticker, start, as_of)
            if not series:
                logger.warning(
                    f"macro-beta: holding {h.ticker} dropped (no price data)"
                )
                # cost_basis is the TOTAL position cost (not per-share), so it is
                # the value proxy directly — do NOT multiply by shares.
                total_value += getattr(h, "cost_basis", 0.0)
                continue
            latest_close = series[-1][1]
            value = h.shares * latest_close
            total_value += value
            rets = daily_returns(series)
            if len(rets) < self._headline:
                continue
            holding_rets[h.ticker] = rets
            values[h.ticker] = value
            covered_value += value

        if not holding_rets:
            return aggregate_macro_exposure(
                as_of=as_of.date().isoformat(),
                factors=factors,
                per_holding=[],
                systematic_share=0.0,
                factor_move_std={},
                book_drift_by_factor={},
                beta_headline_by_factor={},
                total_holdings=len(holdings),
                coverage_value_frac=0.0,
                thresholds=self._thresholds,
            )

        covered_total = sum(values.values())
        weights = {t: v / covered_total for t, v in values.items()}

        for t, rets in holding_rets.items():
            y_h, f_h = align_returns(rets, factor_rets)
            bh = self._fit(y_h, f_h, self._headline)
            br = self._fit(y_h, f_h, self._drift)
            betas = tuple(
                MacroFactorBeta(
                    factor=f,
                    beta_headline=bh[0].get(f, 0.0),
                    beta_recent=br[0].get(f, 0.0),
                    drift=br[0].get(f, 0.0) - bh[0].get(f, 0.0),
                )
                for f in factors
            )
            per_holding.append(
                HoldingMacroExposure(
                    ticker=t, weight=weights[t], betas=betas, r_squared=bh[1]
                )
            )

        factor_dates = sorted({d for d, _ in next(iter(factor_rets.values()))})
        book_rets = book_return_series(holding_rets, weights, factor_dates)
        yb, fb = align_returns(book_rets, factor_rets)
        book_head = self._fit(yb, fb, self._headline)
        book_drift = self._fit(yb, fb, self._drift)
        book_drift_by_factor = {
            f: book_drift[0].get(f, 0.0) - book_head[0].get(f, 0.0) for f in factors
        }

        factor_move_std = {f: _std(fb[f][-self._headline :]) for f in factors}

        stats = self._compute_v8_stats(
            holding_rets=holding_rets,
            weights=weights,
            yb=yb,
            fb=fb,
            book_head=book_head,
            factors=factors,
            as_of=as_of,
            holdings=holdings,
        )

        return aggregate_macro_exposure(
            as_of=as_of.date().isoformat(),
            factors=factors,
            per_holding=per_holding,
            systematic_share=book_head[1],
            factor_move_std=factor_move_std,
            book_drift_by_factor=book_drift_by_factor,
            beta_headline_by_factor=book_head[0],
            total_holdings=len(holdings),
            coverage_value_frac=(covered_value / total_value) if total_value else 0.0,
            thresholds=self._thresholds,
            **stats,
        )

    def _compute_v8_stats(
        self,
        *,
        holding_rets: dict[str, list[tuple[datetime, float]]],
        weights: dict[str, float],
        yb: list[float],
        fb: dict[str, list[float]],
        book_head: tuple[dict[str, float], float],
        factors: tuple[str, ...],
        as_of: datetime,
        holdings: list[Any],
    ) -> dict[str, Any]:
        """Compute the descriptive v8 risk stats. Returns a dict of the new
        BookMacroExposure fields (all neutral defaults when deps/data are absent)."""
        enb = 0.0
        pc_variance: tuple[float, ...] = ()
        pc_labels: tuple[str, ...] = ()
        pc_labels_data_gap = False
        systematic_share_adj = 0.0
        systematic_share_ci: tuple[float, float] = (0.0, 0.0)
        beta_ci_by_factor: dict[str, tuple[float, float]] = {}
        suppressed_factors: tuple[str, ...] = ()
        downside_beta = 0.0
        risk_contribution: dict[str, float] = {}
        vif_by_factor: dict[str, float] = {}
        diversification_ratio = 1.0
        sector_weights: dict[str, float] = {}
        sector_hhi = 0.0
        sector_gaps: tuple[str, ...] = ()
        holdings_meta: tuple[dict[str, object], ...] = ()
        sys_share_history: tuple[tuple[str, float], ...] = ()

        yb_w = yb[-self._headline :]
        fb_w = {f: v[-self._headline :] for f, v in fb.items()}
        n_used = len(yb_w)

        tickers_ordered, rows = aligned_return_matrix(holding_rets)
        weights_vec = [weights[t] for t in tickers_ordered]

        if self._risk is not None:
            systematic_share_adj = adjusted_r2(book_head[1], n=n_used, p=len(factors))
            systematic_share_ci = self._risk.bootstrap_r2_ci(yb_w, fb_w, self._alpha)
            beta_ci_by_factor = self._risk.beta_cis(yb_w, fb_w, self._alpha)
            suppressed_factors = _suppressed_from_ci(beta_ci_by_factor)
            if "SPY" in fb_w:
                downside_beta = self._risk.downside_beta(yb_w, fb_w["SPY"])
            vif_by_factor = {
                f: vif_from_r2(r2) for f, r2 in self._risk.factor_vif_r2(fb_w).items()
            }
            if rows and tickers_ordered:
                eigs = self._risk.covariance_eigenvalues(rows)
                enb = effective_number_of_bets(eigs)
                total_eig = sum(eigs)
                if total_eig > 0:
                    pc_variance = tuple(e / total_eig for e in eigs[:3])
                loadings = self._risk.principal_loadings(rows, tickers_ordered, k=3)
                marginal, port_var = self._risk.risk_contribution_terms(
                    rows, weights_vec
                )
                rc = risk_contributions(weights_vec, marginal, port_var)
                risk_contribution = {
                    t: rc[i] for i, t in enumerate(tickers_ordered) if i < len(rc)
                }
                # diversification ratio: weighted-avg holding vol / book vol
                wavg_vol = sum(
                    weights[t]
                    * _std([r for _, r in holding_rets[t]][-self._headline :])
                    for t in tickers_ordered
                )
                book_vol = _std(yb_w)
                diversification_ratio = _diversification_ratio(wavg_vol, book_vol)
                # PC labels from sector dominance (honest fallback)
                if self._sector is not None:
                    pc_labels, pc_labels_data_gap = _label_principal_components(
                        loadings, self._sector.sector
                    )

        # Sectors + holdings_meta (independent of self._risk; needs sector provider)
        if self._sector is not None:
            sector_weights, sector_hhi, sector_gaps, holdings_meta = _sector_breakdown(
                holdings, weights, self._sector.sector
            )

        # Drift history (read-only; append current point in memory, NOT to disk)
        if self._history_path is not None:
            loaded = load_systematic_share_history(self._history_path)
            sys_share_history = tuple(loaded) + (
                (as_of.date().isoformat(), min(max(book_head[1], 0.0), 1.0)),
            )

        return {
            "enb": enb,
            "pc_variance": pc_variance,
            "pc_labels": pc_labels,
            "pc_labels_data_gap": pc_labels_data_gap,
            "systematic_share_adj": systematic_share_adj,
            "systematic_share_ci": systematic_share_ci,
            "beta_ci_by_factor": beta_ci_by_factor,
            "suppressed_factors": suppressed_factors,
            "downside_beta": downside_beta,
            "risk_contribution": risk_contribution,
            "vif_by_factor": vif_by_factor,
            "diversification_ratio": diversification_ratio,
            "sector_weights": sector_weights,
            "sector_hhi": sector_hhi,
            "sector_gaps": sector_gaps,
            "holdings_meta": holdings_meta,
            "sys_share_history": sys_share_history,
        }

    def _fit(
        self,
        y: list[float],
        factors: dict[str, list[float]],
        window: int,
    ) -> tuple[dict[str, float], float]:
        y_w = y[-window:]
        f_w = {k: v[-window:] for k, v in factors.items()}
        return self._est.estimate(y_w, f_w, self._alpha)  # type: ignore[no-any-return]


def _std(xs: list[float]) -> float:
    if len(xs) < 2:
        return 0.0
    m = sum(xs) / len(xs)
    variance = float(sum((x - m) ** 2 for x in xs)) / (len(xs) - 1)
    return math.sqrt(variance)
