"""ADV-based liquidity terciles + pre-registered slippage schedule (pure).

Liquidity (ADV = avg dollar-volume) replaces market cap as the split axis: it is
fully point-in-time (no shares-outstanding history needed) and is arguably truer
to the structural thesis (liquidity, not cap, is what blocks institutions). See
spec Caveat 1.
"""

from __future__ import annotations

SLIPPAGE_BPS = {"bottom": 150, "mid": 75, "top": 40}


def assign_terciles(adv: dict[str, float]) -> dict[str, str]:
    """Split tickers into bottom/mid/top terciles by ascending ADV.

    Bottom = least liquid (smallest ADV) = the primary-hypothesis tercile.
    Ties broken by ticker for determinism. Boundaries via index thirds.
    """
    if not adv:
        return {}
    ordered = sorted(adv, key=lambda k: (adv[k], k))
    n = len(ordered)
    out: dict[str, str] = {}
    for i, tk in enumerate(ordered):
        if i < n / 3:
            out[tk] = "bottom"
        elif i < 2 * n / 3:
            out[tk] = "mid"
        else:
            out[tk] = "top"
    return out


def slippage_bps_for_tercile(tercile: str) -> int:
    return SLIPPAGE_BPS[tercile]
