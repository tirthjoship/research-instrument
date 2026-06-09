"""Orchestrate the macro-beta scrubber: prices -> returns -> estimate -> aggregate.

Network-free by injection (price_provider + estimator). Reuses the same
price_provider closure as _build_weekly_brief so the brief and the scrubber see
identical price data.
"""

from __future__ import annotations

import math
from datetime import datetime, timedelta
from typing import Any, Callable

from loguru import logger

from domain.macro_beta import (
    aggregate_macro_exposure,
    align_returns,
    book_return_series,
    daily_returns,
)
from domain.models import BookMacroExposure, HoldingMacroExposure, MacroFactorBeta

PriceProvider = Callable[[str, datetime, datetime], "list[tuple[datetime, float]]"]


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
    ) -> None:
        self._prices = price_provider
        self._est = estimator
        self._factors = factors
        self._alpha = alpha
        self._headline = headline_window
        self._drift = drift_window
        self._thresholds = thresholds
        self._history_days = history_days

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
        )

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
