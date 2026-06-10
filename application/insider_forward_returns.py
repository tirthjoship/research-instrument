"""Resolve cluster events to 21-trading-day forward returns + trailing ADV.

Survivorship-safe (spec sec.5). The key honesty rule, post code-review C1: ADV is
computed from the TRAILING window, independently of whether the forward window
exists. So a name that delists mid-holding-period still gets a trailing ADV (hence
a tercile) and therefore lands in the coverage DENOMINATOR — it just contributes
no forward abnormal return (it lowers coverage instead of vanishing from it).

`resolve_events` returns two lists:
- `records`: every event with an obtainable trailing ADV. Each carries `adv` plus
  `fwd_return`/`entry_date`/`exit_date` that are None when the forward window is
  missing (delisted before +21d). These are tercile-assignable.
- `no_price`: events with no price bar at/after the fire date at all (delisted
  before the fire, or an unmapped symbol). Not tercile-assignable; the caller
  bins these into the bottom (least-liquid) tercile denominator as the
  conservative survivorship assumption, so they can only lower coverage.

The price source is a callable so the unit tests with fakes; production wraps
yfinance get_signals.
"""

from __future__ import annotations

import math
from collections.abc import Callable
from datetime import date

from domain.insider_cluster import ClusterEvent

FORWARD_HORIZON_TDAYS = 21
ADV_LOOKBACK_TDAYS = 21

PriceFn = Callable[[str], list[tuple[date, float, float]]]  # (date, close, volume)


def resolve_events(
    events: list[ClusterEvent], prices: PriceFn
) -> tuple[list[dict[str, object]], list[ClusterEvent]]:
    """Resolve events to (records-with-ADV, no-price events). See module docstring."""
    records: list[dict[str, object]] = []
    no_price: list[ClusterEvent] = []
    for ev in events:
        series = sorted(prices(ev.ticker), key=lambda r: r[0])
        idx = next((i for i, r in enumerate(series) if r[0] >= ev.fire_date), None)
        if idx is None:
            # No bar at/after the fire date: delisted before fire, or unmapped
            # symbol. Cannot assign a tercile; caller bins to bottom (worst case).
            no_price.append(ev)
            continue

        # Trailing ADV — computable from the lookback alone (no forward needed).
        lookback = series[max(0, idx - ADV_LOOKBACK_TDAYS) : idx] or series[: idx + 1]
        adv = sum(close * vol for _, close, vol in lookback) / len(lookback)
        if not math.isfinite(adv):
            # A NaN/inf bar would silently misbin the event's tercile (NaN breaks
            # sorted-rank binning). Treat as unpriceable: conservative bottom-
            # denominator path, same as a missing series.
            no_price.append(ev)
            continue

        # Forward 21d return — only if the forward window exists and entry > 0.
        c0 = series[idx][1]
        fwd_return: float | None = None
        entry_date: date | None = None
        exit_date: date | None = None
        if c0 > 0 and idx + FORWARD_HORIZON_TDAYS < len(series):
            c1 = series[idx + FORWARD_HORIZON_TDAYS][1]
            fwd_return = (c1 - c0) / c0
            entry_date = series[idx][0]
            exit_date = series[idx + FORWARD_HORIZON_TDAYS][0]

        records.append(
            {
                "ticker": ev.ticker,
                "fire_date": ev.fire_date,
                "adv": adv,
                "fwd_return": fwd_return,
                "entry_date": entry_date,
                "exit_date": exit_date,
            }
        )
    return records, no_price


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
