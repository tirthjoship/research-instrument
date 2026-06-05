from datetime import datetime

from domain.event_service import event_conviction_score
from domain.models import ClassifiedEvent, EventCategory, EventSectorImpact

_CAT = EventCategory.GOVERNMENT_INVESTMENT


def _impact(mag: float = 0.5, hl: float = 5.0) -> EventSectorImpact:
    return EventSectorImpact(
        category=_CAT,
        sector="Technology",
        magnitude=mag,
        half_life_days=hl,
        sample_count=20,
    )


def test_no_events_is_neutral():
    assert event_conviction_score([], "Technology", {}, datetime(2026, 6, 4)) == 5.0


def test_fresh_bullish_event_raises_score():
    ev = ClassifiedEvent(
        "US takes stake in chipmaker", "2026-06-04", _CAT, 1, 0.9, "rss"
    )
    impacts = {(_CAT, "Technology"): _impact()}
    assert (
        event_conviction_score([ev], "Technology", impacts, datetime(2026, 6, 4)) > 5.0
    )


def test_bearish_event_lowers_score():
    ev = ClassifiedEvent("h", "2026-06-04", _CAT, -1, 0.9, "rss")
    impacts = {(_CAT, "Technology"): _impact()}
    assert (
        event_conviction_score([ev], "Technology", impacts, datetime(2026, 6, 4)) < 5.0
    )


def test_stale_event_decays_toward_neutral():
    impacts = {(_CAT, "Technology"): _impact(hl=5.0)}
    fresh = ClassifiedEvent("h", "2026-06-04", _CAT, 1, 0.9, "rss")
    stale = ClassifiedEvent("h", "2026-05-01", _CAT, 1, 0.9, "rss")
    now = datetime(2026, 6, 4)
    assert event_conviction_score(
        [fresh], "Technology", impacts, now
    ) > event_conviction_score([stale], "Technology", impacts, now)


def test_no_matching_sector_impact_is_neutral():
    ev = ClassifiedEvent("h", "2026-06-04", _CAT, 1, 0.9, "rss")
    assert event_conviction_score([ev], "Energy", {}, datetime(2026, 6, 4)) == 5.0
