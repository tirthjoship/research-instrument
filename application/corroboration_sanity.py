"""3-6mo retrospective on DATED sources only. Sanity signal, never a verdict (spec §8)."""

from __future__ import annotations

from datetime import date


def dated_source_hit_rate(
    events: list[tuple[str, date, str, float]],
) -> dict[str, object]:
    """Compute hit rate for dated source events.

    A "hit" is: bullish stance AND positive return, OR bearish stance AND negative return.

    Args:
        events: list of (ticker, event_date, stance_str, actual_return).

    Returns:
        Dict with keys ``n``, ``hit_rate``, ``label``.  ``label`` is always
        ``"SANITY-NOT-VERDICT"`` — this metric is a calibration signal only.
    """
    n = len(events)
    hits = sum(
        1
        for _, _, stance, ret in events
        if (stance == "bullish" and ret > 0) or (stance == "bearish" and ret < 0)
    )
    return {
        "n": n,
        "hit_rate": (hits / n if n else 0.0),
        "label": "SANITY-NOT-VERDICT",
    }
