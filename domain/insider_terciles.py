"""ADV-based liquidity terciles + pre-registered slippage schedule (pure).

Liquidity (ADV = avg dollar-volume) replaces market cap as the split axis: it is
fully point-in-time (no shares-outstanding history needed) and is arguably truer
to the structural thesis (liquidity, not cap, is what blocks institutions). See
spec Caveat 1. Binning is per-event and point-in-time expanding (M2): see `tercile_for_event`.
"""

from __future__ import annotations

SLIPPAGE_BPS = {"bottom": 150, "mid": 75, "top": 40}


def tercile_for_event(prior_advs: list[float], adv: float) -> str:
    """Bin one event's ADV against its point-in-time distribution (M2, spec §3).

    Distribution = ADVs of all events with fire_date <= this event's, INCLUDING
    itself (the caller appends in fire-date order). Rank fraction = first-occurrence
    index in the sorted distribution / n, so ties bin LOW — conservative toward
    bottom, the primary-hypothesis tercile. A 2006 event is therefore never binned
    using the 2006-2024 pooled distribution.
    """
    dist = sorted(prior_advs + [adv])
    frac = dist.index(adv) / len(dist)
    if frac < 1 / 3:
        return "bottom"
    if frac < 2 / 3:
        return "mid"
    return "top"


def slippage_bps_for_tercile(tercile: str) -> int:
    return SLIPPAGE_BPS[tercile]
