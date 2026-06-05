"""Event -> conviction sub-score. Pure functions, no I/O."""

from __future__ import annotations

from datetime import datetime

from domain.models import ClassifiedEvent, EventCategory, EventSectorImpact


def event_conviction_score(
    events: list[ClassifiedEvent],
    sector: str,
    impacts: dict[tuple[EventCategory, str], EventSectorImpact],
    now: datetime,
) -> float:
    """Aggregate classified events into a 1-10 conviction sub-score.

    Each event contributes direction * confidence * learned-magnitude, decayed
    exponentially by age using the impact's half-life. No events, or no matching
    sector impact, yields the neutral 5.0.
    """
    if not events:
        return 5.0
    signal = 0.0
    for ev in events:
        impact = impacts.get((ev.category, sector))
        if impact is None:
            continue
        age_days = (now - datetime.strptime(ev.event_date, "%Y-%m-%d")).days
        decay = 0.5 ** (max(age_days, 0) / impact.half_life_days)
        signal += ev.direction * ev.confidence * impact.magnitude * decay
    return max(1.0, min(10.0, 5.0 + signal * 5.0))
