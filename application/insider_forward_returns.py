"""Resolve cluster events to 21-trading-day forward returns + trailing ADV.

Survivorship-safe: a name with no obtainable forward price is returned in the
`unresolved` list, never silently dropped (spec sec.5). The price source is a
callable so the unit tests with fakes; production wraps yfinance get_signals.
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import date

from domain.insider_cluster import ClusterEvent

FORWARD_HORIZON_TDAYS = 21
ADV_LOOKBACK_TDAYS = 21

PriceFn = Callable[[str], list[tuple[date, float, float]]]  # (date, close, volume)


def resolve_events(
    events: list[ClusterEvent], prices: PriceFn
) -> tuple[list[dict[str, object]], list[ClusterEvent]]:
    resolved: list[dict[str, object]] = []
    unresolved: list[ClusterEvent] = []
    for ev in events:
        series = sorted(prices(ev.ticker), key=lambda r: r[0])
        idx = next((i for i, r in enumerate(series) if r[0] >= ev.fire_date), None)
        if idx is None or idx + FORWARD_HORIZON_TDAYS >= len(series):
            unresolved.append(ev)
            continue
        c0 = series[idx][1]
        c1 = series[idx + FORWARD_HORIZON_TDAYS][1]
        if c0 <= 0:
            unresolved.append(ev)
            continue
        lookback = series[max(0, idx - ADV_LOOKBACK_TDAYS) : idx] or series[: idx + 1]
        adv = sum(close * vol for _, close, vol in lookback) / len(lookback)
        resolved.append(
            {
                "ticker": ev.ticker,
                "fire_date": ev.fire_date,
                "fwd_return": (c1 - c0) / c0,
                "adv": adv,
                "entry_date": series[idx][0],
                "exit_date": series[idx + FORWARD_HORIZON_TDAYS][0],
            }
        )
    return resolved, unresolved


def benchmark_return(
    prices: PriceFn, etf: str, entry_date: date, exit_date: date
) -> float | None:
    """21-tday return of the benchmark ETF over the same window. None if uncovered."""
    series = sorted(prices(etf), key=lambda r: r[0])
    entry = next((c for d, c, _ in series if d >= entry_date and c > 0), None)
    exit_ = next((c for d, c, _ in series if d >= exit_date and c > 0), None)
    if entry is None or exit_ is None:
        return None
    return (exit_ - entry) / entry
