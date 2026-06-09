"""Point-in-time panel builder for the evidence-screen IC backtest.

HONESTY CONSTRAINT (project rule #2 — no look-ahead bias):
Only the MOMENTUM factor has clean point-in-time history derivable from prices.
The other three composite factors (revision/quality/value) require point-in-time
fundamentals / analyst snapshots that yfinance cannot supply for 2018-2026.
Using current values at past dates would be catastrophic look-ahead bias.
Therefore the composite is built from the MOMENTUM leg ONLY; revision, quality,
and value are flagged-neutral (None), exactly as the live domain composite_score
handles missing factors.  The caller is responsible for stating this caveat.
"""

from __future__ import annotations

import calendar
from datetime import datetime, timedelta
from typing import Callable

from application.price_returns import compute_forward_return
from domain.factor_scores import composite_score, zscore
from domain.trend_rules import momentum_12_1

__all__ = ["monthly_closes_asof", "build_screen_panels"]

# ---------------------------------------------------------------------------
# Pure helper
# ---------------------------------------------------------------------------


def monthly_closes_asof(
    series: list[tuple[datetime, float]], as_of: datetime
) -> list[float]:
    """From an ascending (date, close) daily series, return the last close of each
    calendar month whose month-end date is <= as_of, ascending.

    Point-in-time guarantee: never uses any close after as_of.
    Returns an empty list when no eligible closes exist.
    """
    # Group daily closes by (year, month); keep the last close per month.
    monthly_last: dict[tuple[int, int], float] = {}
    for d, c in series:
        if d <= as_of:
            key = (d.year, d.month)
            # Overwrite so the highest date in the month wins (series is ascending)
            monthly_last[key] = c

    # Filter: only keep months whose last calendar day is <= as_of.
    # (A month-end is the last day of the calendar month.)
    result: list[float] = []
    for (yr, mo), close in sorted(monthly_last.items()):
        last_day = calendar.monthrange(yr, mo)[1]
        month_end = datetime(yr, mo, last_day, 23, 59, 59)
        if month_end <= as_of:
            result.append(close)
    return result


# ---------------------------------------------------------------------------
# Panel builder
# ---------------------------------------------------------------------------


def build_screen_panels(
    tickers: list[str],
    dates: list[datetime],
    price_series_fn: Callable[[str], list[tuple[datetime, float]]],
    horizon_days: int = 21,
    benchmark_ticker: str = "SPY",
) -> tuple[list[dict[str, tuple[float, float]]], list[float]]:
    """Build point-in-time IC panels for ScreenBacktestUseCase.

    For each date in *dates*, builds a cross-sectional panel:
        {ticker: (composite_signal, forward_return)}

    composite_signal is built from the MOMENTUM leg only — see module docstring
    for the look-ahead-bias honesty constraint.  rank-IC results are therefore
    identical to ranking on raw momentum; we still route through zscore +
    composite_score for domain-layer fidelity.

    A ticker is included for a date only if:
      - momentum_12_1(monthly_closes_asof(series, date)) is not None, AND
      - compute_forward_return(series, date, horizon_days) != 0.0 (has exit price).

    Empty panels (no eligible tickers) are still appended as {} so indices
    align with benchmark_returns.

    Args:
        tickers: Ticker symbols to include (benchmark_ticker is handled separately).
        dates: Evaluation dates, ascending.
        price_series_fn: Callable(ticker) -> ascending (date, close) series.
                         Called once per unique ticker; the caller is expected
                         to cache the full historical range.
        horizon_days: Forward-return horizon in calendar days.
        benchmark_ticker: Ticker to use as the per-date market return baseline.

    Returns:
        (panels, benchmark_returns)
        panels: list[dict] aligned with dates.
        benchmark_returns: per-date benchmark forward return; 0.0 if unavailable.
        len(benchmark_returns) == len(dates).
    """
    # Pre-fetch benchmark series once.
    bench_series = price_series_fn(benchmark_ticker)

    panels: list[dict[str, tuple[float, float]]] = []
    benchmark_returns: list[float] = []

    for as_of in dates:
        # Benchmark return for this date (0.0 if unavailable)
        bfwd = compute_forward_return(bench_series, as_of, horizon_days)
        benchmark_returns.append(bfwd)

        # Build per-ticker raw momentum values for cross-sectional z-scoring
        eligible: list[tuple[str, float, float]] = []  # (ticker, raw_mom, fwd_ret)
        for ticker in tickers:
            series = price_series_fn(ticker)
            closes = monthly_closes_asof(series, as_of)
            raw_mom = momentum_12_1(closes)
            if raw_mom is None:
                continue
            fwd = compute_forward_return(series, as_of, horizon_days)
            # Exclude if forward return is unavailable (no exit price yet)
            if fwd == 0.0 and not _has_exit_price(series, as_of, horizon_days):
                continue
            eligible.append((ticker, raw_mom, fwd))

        if not eligible:
            panels.append({})
            continue

        # Cross-sectional z-score of momentum
        raw_moms = [e[1] for e in eligible]
        zscored = zscore(raw_moms)

        panel: dict[str, tuple[float, float]] = {}
        for (ticker, _raw, fwd), z_val in zip(eligible, zscored):
            # Route through composite_score for domain-layer fidelity.
            # Only momentum leg populated; others flagged-neutral (None).
            sig = composite_score(
                {"momentum": z_val, "revision": None, "quality": None, "value": None}
            )
            panel[ticker] = (sig, fwd)

        panels.append(panel)

    return panels, benchmark_returns


# ---------------------------------------------------------------------------
# Private helper
# ---------------------------------------------------------------------------


def _has_exit_price(
    series: list[tuple[datetime, float]], entry_date: datetime, horizon_days: int
) -> bool:
    """True if there is at least one close on or after entry_date + horizon_days."""
    exit_target = entry_date + timedelta(days=horizon_days)
    for d, _c in series:
        if d >= exit_target:
            return True
    return False
