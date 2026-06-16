"""Point-in-time panel builder for the evidence-screen IC backtest.

HONESTY CONSTRAINT (project rule #2 — no look-ahead bias):
Only MOMENTUM and LOWVOL factors have clean point-in-time history derivable from prices.
The other three composite factors (revision/quality/value) require point-in-time
fundamentals / analyst snapshots that yfinance cannot supply for 2018-2026.
Using current values at past dates would be catastrophic look-ahead bias.
Therefore the composite is built from MOMENTUM + LOWVOL only; revision, quality,
and value are flagged-neutral (None), exactly as the live domain composite_score
handles missing factors.  The caller is responsible for stating this caveat.
"""

from __future__ import annotations

import calendar
from datetime import datetime, timedelta
from typing import Callable

from application.price_returns import compute_forward_return
from domain.factor_scores import composite_score, zscore
from domain.trend_rules import momentum_12_1, trailing_volatility

__all__ = ["monthly_closes_asof", "daily_closes_asof", "build_screen_panels"]

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


def daily_closes_asof(
    series: list[tuple[datetime, float]], as_of: datetime
) -> list[float]:
    """Extract daily close prices from *series* with date <= *as_of* (PIT-safe).

    Returns closes in ascending date order.  Used for trailing_volatility (lowvol
    factor) which requires >= 61 daily closes.
    """
    return [c for d, c in series if d <= as_of]


# ---------------------------------------------------------------------------
# Panel builder
# ---------------------------------------------------------------------------


def build_screen_panels(
    tickers: list[str],
    dates: list[datetime],
    price_series_fn: Callable[[str], list[tuple[datetime, float]]],
    horizon_days: int = 21,
    benchmark_ticker: str = "SPY",
) -> tuple[list[dict[str, tuple[float, float, float | None]]], list[float]]:
    """Build point-in-time IC panels for ScreenBacktestUseCase.

    For each date in *dates*, builds a cross-sectional panel:
        {ticker: (composite_signal, forward_return, lowvol_z)}

    composite_signal is built from MOMENTUM + LOWVOL (both PIT-safe from price
    history); revision, quality, value remain None — see module docstring for the
    look-ahead-bias honesty constraint.

    lowvol_z: cross-sectional z-score of (-trailing_volatility) for each eligible
    ticker, or None when the ticker has insufficient daily history (<61 closes).

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
            Each entry is (composite_signal, forward_return, lowvol_z_or_none).
        benchmark_returns: per-date benchmark forward return; 0.0 if unavailable.
        len(benchmark_returns) == len(dates).
    """
    # Pre-fetch benchmark series once.
    bench_series = price_series_fn(benchmark_ticker)

    panels: list[dict[str, tuple[float, float, float | None]]] = []
    benchmark_returns: list[float] = []

    for as_of in dates:
        # Benchmark return for this date (0.0 if unavailable)
        bfwd = compute_forward_return(bench_series, as_of, horizon_days)
        benchmark_returns.append(bfwd)

        # Build per-ticker raw signal values for cross-sectional z-scoring
        # (ticker, raw_mom, fwd_ret, raw_neg_vol)
        eligible: list[tuple[str, float, float, float | None]] = []
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
            # lowvol: PIT-safe — only daily closes <= as_of
            daily = daily_closes_asof(series, as_of)
            vol = trailing_volatility(daily)
            raw_neg_vol: float | None = -vol if vol is not None else None
            eligible.append((ticker, raw_mom, fwd, raw_neg_vol))

        if not eligible:
            panels.append({})
            continue

        # Cross-sectional z-score of momentum
        raw_moms = [e[1] for e in eligible]
        zmom = zscore(raw_moms)

        # Cross-sectional z-score of lowvol (None-safe: only z-score present values)
        raw_neg_vols: list[float | None] = [e[3] for e in eligible]
        present_vols = [v for v in raw_neg_vols if v is not None]
        if len(present_vols) >= 2:
            zv_present = zscore(present_vols)
            it = iter(zv_present)
            zlowvol: list[float | None] = [
                next(it) if v is not None else None for v in raw_neg_vols
            ]
        else:
            zlowvol = [None] * len(eligible)

        panel: dict[str, tuple[float, float, float | None]] = {}
        for (ticker, _raw_mom, fwd, _negvol), z_mom, z_lv in zip(
            eligible, zmom, zlowvol
        ):
            # Route through composite_score for domain-layer fidelity.
            # MOMENTUM + LOWVOL are PIT-safe price-derived; revision/quality/value = None.
            sig = composite_score(
                {
                    "momentum": z_mom,
                    "revision": None,
                    "quality": None,
                    "value": None,
                    "lowvol": z_lv,
                }
            )
            panel[ticker] = (sig, fwd, z_lv)

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
