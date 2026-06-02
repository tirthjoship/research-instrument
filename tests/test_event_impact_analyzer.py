"""Tests for EventImpactAnalyzer — learns impact magnitude + decay from historical data."""

from __future__ import annotations

from adapters.ml.event_impact_analyzer import EventImpactAnalyzer
from domain.models import ClassifiedEvent, EventCategory, EventSectorImpact


def _make_event(
    category: EventCategory, date: str, direction: int = 1
) -> ClassifiedEvent:
    return ClassifiedEvent(
        headline="test",
        event_date=date,
        category=category,
        direction=direction,
        confidence=0.9,
        source="test",
    )


class TestLearnImpact:
    def test_learns_magnitude_from_returns(self) -> None:
        """Given events and sector returns, learns positive magnitude."""
        analyzer = EventImpactAnalyzer()
        events = [
            _make_event(EventCategory.EARNINGS_SURPRISE, "2025-01-10"),
            _make_event(EventCategory.EARNINGS_SURPRISE, "2025-03-15"),
            _make_event(EventCategory.EARNINGS_SURPRISE, "2025-06-20"),
        ]
        # Sector returns after each event: day1, day2, ... day10
        sector_returns = {
            "2025-01-10": [0.02, 0.015, 0.01, 0.005, 0.003, 0.001, 0.0, 0.0, 0.0, 0.0],
            "2025-03-15": [
                0.025,
                0.018,
                0.012,
                0.006,
                0.002,
                0.001,
                0.0,
                0.0,
                0.0,
                0.0,
            ],
            "2025-06-20": [
                0.018,
                0.013,
                0.008,
                0.004,
                0.002,
                0.001,
                0.0,
                0.0,
                0.0,
                0.0,
            ],
        }
        impact = analyzer.learn_impact(
            events=events,
            sector="Technology",
            sector_returns_by_date=sector_returns,
        )
        assert impact is not None
        assert impact.magnitude > 0
        assert impact.half_life_days > 0
        assert impact.sample_count == 3

    def test_learns_half_life(self) -> None:
        """Half-life should reflect decay speed."""
        analyzer = EventImpactAnalyzer()
        # Fast decay events
        fast_events = [
            _make_event(EventCategory.MACRO_DATA, f"2025-0{i+1}-01") for i in range(5)
        ]
        fast_returns = {
            f"2025-0{i+1}-01": [0.02, 0.005, 0.001, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0]
            for i in range(5)
        }
        fast_impact = analyzer.learn_impact(fast_events, "Financials", fast_returns)
        assert fast_impact is not None
        assert fast_impact.half_life_days < 5.0

    def test_too_few_events_returns_none(self) -> None:
        """Need at least 3 events to learn impact."""
        analyzer = EventImpactAnalyzer(min_events=3)
        events = [_make_event(EventCategory.FDA_APPROVAL, "2025-01-01")]
        returns = {"2025-01-01": [0.03] * 10}
        impact = analyzer.learn_impact(events, "Healthcare", returns)
        assert impact is None

    def test_no_returns_data_returns_none(self) -> None:
        analyzer = EventImpactAnalyzer()
        events = [
            _make_event(EventCategory.FDA_APPROVAL, f"2025-0{i+1}-01") for i in range(5)
        ]
        impact = analyzer.learn_impact(events, "Healthcare", {})
        assert impact is None


class TestDecayComputation:
    def test_decay_at_zero_is_full_magnitude(self) -> None:
        analyzer = EventImpactAnalyzer()
        impact = EventSectorImpact(
            category=EventCategory.TARIFF_TRADE,
            sector="Energy",
            magnitude=0.02,
            half_life_days=3.0,
            sample_count=10,
        )
        decay = analyzer.compute_decay(impact, days_since_event=0)
        assert abs(decay - 0.02) < 1e-6

    def test_decay_at_half_life_is_half(self) -> None:
        analyzer = EventImpactAnalyzer()
        impact = EventSectorImpact(
            category=EventCategory.TARIFF_TRADE,
            sector="Energy",
            magnitude=0.02,
            half_life_days=3.0,
            sample_count=10,
        )
        decay = analyzer.compute_decay(impact, days_since_event=3)
        assert abs(decay - 0.01) < 1e-6

    def test_decay_approaches_zero(self) -> None:
        analyzer = EventImpactAnalyzer()
        impact = EventSectorImpact(
            category=EventCategory.TARIFF_TRADE,
            sector="Energy",
            magnitude=0.02,
            half_life_days=3.0,
            sample_count=10,
        )
        decay = analyzer.compute_decay(impact, days_since_event=30)
        assert decay < 0.0001


class TestLoadSectorMapping:
    def test_loads_mapping_yaml(self, tmp_path) -> None:
        content = """
mappings:
  earnings_surprise:
    - sector: Technology
      direction: 1
  tariff_trade:
    - sector: Energy
      direction: 1
    - sector: Technology
      direction: -1
"""
        path = tmp_path / "mapping.yaml"
        path.write_text(content)
        analyzer = EventImpactAnalyzer(sector_mapping_path=str(path))
        mapping = analyzer.get_affected_sectors(EventCategory.TARIFF_TRADE)
        assert len(mapping) == 2
        sectors = {m["sector"] for m in mapping}
        assert "Energy" in sectors
        assert "Technology" in sectors

    def test_unknown_category_returns_empty(self, tmp_path) -> None:
        content = "mappings:\n  earnings_surprise:\n    - sector: Technology\n      direction: 1\n"
        path = tmp_path / "mapping.yaml"
        path.write_text(content)
        analyzer = EventImpactAnalyzer(sector_mapping_path=str(path))
        mapping = analyzer.get_affected_sectors(EventCategory.FDA_APPROVAL)
        assert mapping == []
