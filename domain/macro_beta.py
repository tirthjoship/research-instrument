"""Pure macro-beta math (no IO, stdlib only).

Returns/alignment/book-aggregation/flag-policy for the macro-beta scrubber
(Unit A, ADR-052). The Ridge fit itself lives in the adapter; this module only
does deterministic arithmetic so it is fully unit- and property-testable.
"""

from __future__ import annotations

from datetime import datetime

from domain.models import BookMacroExposure, HoldingMacroExposure, MacroBetaFlag

_MIN_DRIFT_BETA = (
    0.15  # below this exposure, drift ratio is noise — suppress DRIFT flag
)


def aligned_return_matrix(
    holding_returns: dict[str, list[tuple[datetime, float]]],
) -> tuple[list[str], list[list[float]]]:
    """Holdings return matrix over dates present in EVERY holding series.

    Returns (tickers, rows) where tickers is the column order and rows[i] is the
    cross-sectional return vector on common date i (rows ascending by date).
    Empty/degenerate (no holdings or no common dates) → (tickers, []).
    """
    tickers = list(holding_returns)
    if not tickers:
        return (tickers, [])
    date_maps: dict[str, dict[datetime, float]] = {
        t: dict(holding_returns[t]) for t in tickers
    }
    common: set[datetime] = set(date_maps[tickers[0]].keys())
    for t in tickers[1:]:
        common &= date_maps[t].keys()
    if not common:
        return (tickers, [])
    rows = [[date_maps[t][d] for t in tickers] for d in sorted(common)]
    return (tickers, rows)


def daily_returns(
    series: list[tuple[datetime, float]],
) -> list[tuple[datetime, float]]:
    """Simple daily returns between consecutive closes. `series` ascending by date.

    A step is dropped when the previous close is 0 (undefined return). The
    returned date is the *later* date of each consecutive pair.
    """
    out: list[tuple[datetime, float]] = []
    for (_, prev), (d, cur) in zip(series, series[1:]):
        if prev == 0:
            continue
        out.append((d, (cur - prev) / prev))
    return out


def align_returns(
    y_returns: list[tuple[datetime, float]],
    factor_returns: dict[str, list[tuple[datetime, float]]],
) -> tuple[list[float], dict[str, list[float]]]:
    """Inner-join y and all factor return series on common dates (ascending).

    Returns (y_aligned, {factor: aligned}) over dates present in EVERY series.
    """
    common: set[datetime] = {d for d, _ in y_returns}
    for series in factor_returns.values():
        common &= {d for d, _ in series}
    dates = sorted(common)
    y_map = dict(y_returns)
    f_maps = {f: dict(s) for f, s in factor_returns.items()}
    y_out = [y_map[d] for d in dates]
    f_out = {f: [f_maps[f][d] for d in dates] for f in factor_returns}
    return y_out, f_out


def book_return_series(
    holding_returns: dict[str, list[tuple[datetime, float]]],
    weights: dict[str, float],
    dates: list[datetime],
) -> list[tuple[datetime, float]]:
    """Dollar-weighted book return per date over `dates`.

    On each date, weights are renormalized over holdings that have a return that
    day (ragged histories handled honestly — a missing holding does not pin the
    book return to 0). Dates with no holdings present are skipped.
    """
    maps = {t: dict(s) for t, s in holding_returns.items()}
    out: list[tuple[datetime, float]] = []
    for d in dates:
        present = [(t, weights.get(t, 0.0)) for t in maps if d in maps[t]]
        wsum = sum(w for _, w in present)
        if wsum <= 0:
            continue
        r = sum((w / wsum) * maps[t][d] for t, w in present)
        out.append((d, r))
    return out


def net_beta(
    per_holding: list[HoldingMacroExposure], factors: tuple[str, ...]
) -> dict[str, float]:
    """Dollar-weighted net beta per factor: Sum_i weight_i * beta_headline_i,k."""
    out: dict[str, float] = {f: 0.0 for f in factors}
    for h in per_holding:
        bmap = {b.factor: b.beta_headline for b in h.betas}
        for f in factors:
            out[f] += h.weight * bmap.get(f, 0.0)
    return out


def build_flags(
    *,
    net_beta_by_factor: dict[str, float],
    systematic_share: float,
    factor_move_std: dict[str, float],
    book_drift_by_factor: dict[str, float],
    beta_headline_by_factor: dict[str, float],
    systematic_share_threshold: float,
    factor_dominance_threshold: float,
    drift_threshold: float,
) -> tuple[MacroBetaFlag, ...]:
    """Apply the heuristic surfacing policy. Thresholds are dials, not edges."""
    flags: list[MacroBetaFlag] = []

    if systematic_share > systematic_share_threshold:
        flags.append(
            MacroBetaFlag(
                kind="SYSTEMATIC_DOMINANT",
                factor=None,
                message=(
                    f"{systematic_share:.0%} of book variance is macro-explained — "
                    f"these are a few factor bets, not independent ideas"
                ),
                value=systematic_share,
                threshold=systematic_share_threshold,
            )
        )

    for f, beta in net_beta_by_factor.items():
        implied = abs(beta) * factor_move_std.get(f, 0.0)
        if implied > factor_dominance_threshold:
            flags.append(
                MacroBetaFlag(
                    kind="FACTOR_DOMINANCE",
                    factor=f,
                    message=(
                        f"net {f} exposure dominates: a 1-sigma {f} move shifts the "
                        f"book ~{implied:.0%}"
                    ),
                    value=implied,
                    threshold=factor_dominance_threshold,
                )
            )

    for f, drift in book_drift_by_factor.items():
        headline = beta_headline_by_factor.get(f, 0.0)
        # Negligible 1-year exposure → drift ratio is noise (denominator ~0); skip.
        if abs(headline) < _MIN_DRIFT_BETA:
            continue
        denom = max(abs(headline), 1e-6)
        ratio = abs(drift) / denom
        if ratio > drift_threshold:
            flags.append(
                MacroBetaFlag(
                    kind="DRIFT",
                    factor=f,
                    message=(
                        f"{f} exposure shifting fast — 63-day beta diverges "
                        f"{ratio:.0%} from the 1-year beta"
                    ),
                    value=ratio,
                    threshold=drift_threshold,
                )
            )

    return tuple(flags)


def aggregate_macro_exposure(
    *,
    as_of: str,
    factors: tuple[str, ...],
    per_holding: list[HoldingMacroExposure],
    systematic_share: float,
    factor_move_std: dict[str, float],
    book_drift_by_factor: dict[str, float],
    beta_headline_by_factor: dict[str, float],
    total_holdings: int,
    coverage_value_frac: float,
    thresholds: dict[str, float],
    # v8 risk-stats fields — all defaulted so existing callers stay unchanged
    enb: float = 0.0,
    pc_variance: tuple[float, ...] = (),
    pc_labels: tuple[str, ...] = (),
    pc_labels_data_gap: bool = False,
    systematic_share_adj: float = 0.0,
    systematic_share_ci: tuple[float, float] = (0.0, 0.0),
    beta_ci_by_factor: dict[str, tuple[float, float]] | None = None,
    suppressed_factors: tuple[str, ...] = (),
    downside_beta: float = 0.0,
    risk_contribution: dict[str, float] | None = None,
    vif_by_factor: dict[str, float] | None = None,
    diversification_ratio: float = 1.0,
    sector_weights: dict[str, float] | None = None,
    sector_hhi: float = 0.0,
    sector_gaps: tuple[str, ...] = (),
    holdings_meta: tuple[dict[str, object], ...] = (),
    sys_share_history: tuple[tuple[str, float], ...] = (),
) -> BookMacroExposure:
    """Assemble the book-level exposure summary from pure pieces."""
    nb = net_beta(per_holding, factors)
    share = min(max(systematic_share, 0.0), 1.0)
    dominant = max(nb, key=lambda f: abs(nb[f])) if per_holding and nb else None
    flags = build_flags(
        net_beta_by_factor=nb,
        systematic_share=share,
        factor_move_std=factor_move_std,
        book_drift_by_factor=book_drift_by_factor,
        beta_headline_by_factor=beta_headline_by_factor,
        systematic_share_threshold=thresholds["systematic_share_threshold"],
        factor_dominance_threshold=thresholds["factor_dominance_threshold"],
        drift_threshold=thresholds["drift_threshold"],
    )
    return BookMacroExposure(
        as_of=as_of,
        factors=factors,
        net_beta_by_factor=nb,
        systematic_share=share,
        idiosyncratic_share=1.0 - share,
        dominant_factor=dominant,
        flags=flags,
        holdings=tuple(per_holding),
        coverage_holdings=len(per_holding),
        total_holdings=total_holdings,
        coverage_value_frac=coverage_value_frac,
        # v8 risk-stats fields
        enb=enb,
        pc_variance=pc_variance,
        pc_labels=pc_labels,
        pc_labels_data_gap=pc_labels_data_gap,
        systematic_share_adj=systematic_share_adj,
        systematic_share_ci=systematic_share_ci,
        beta_ci_by_factor=beta_ci_by_factor if beta_ci_by_factor is not None else {},
        suppressed_factors=suppressed_factors,
        downside_beta=downside_beta,
        risk_contribution=risk_contribution if risk_contribution is not None else {},
        vif_by_factor=vif_by_factor if vif_by_factor is not None else {},
        diversification_ratio=diversification_ratio,
        sector_weights=sector_weights if sector_weights is not None else {},
        sector_hhi=sector_hhi,
        sector_gaps=sector_gaps,
        holdings_meta=holdings_meta,
        sys_share_history=sys_share_history,
    )
