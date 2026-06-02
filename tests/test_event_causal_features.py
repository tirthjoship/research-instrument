"""Tests for EventCausalFeatureEngineer — 8 event-causal features."""

from __future__ import annotations

import pytest

from adapters.ml.event_causal_features import (
    EVENT_CAUSAL_FEATURE_NAMES,
    EventCausalFeatureEngineer,
)
from adapters.ml.event_impact_analyzer import EventImpactAnalyzer
from domain.models import ClassifiedEvent, EventCategory, EventSectorImpact


def _make_event(
    category: EventCategory, date: str, direction: int = 1, confidence: float = 0.9
) -> ClassifiedEvent:
    return ClassifiedEvent(
        headline="test",
        event_date=date,
        category=category,
        direction=direction,
        confidence=confidence,
        source="test",
    )


def _make_impact(
    category: EventCategory,
    sector: str,
    magnitude: float = 0.02,
    half_life: float = 3.0,
    samples: int = 10,
) -> EventSectorImpact:
    return EventSectorImpact(
        category=category,
        sector=sector,
        magnitude=magnitude,
        half_life_days=half_life,
        sample_count=samples,
    )


@pytest.fixture()
def analyzer(tmp_path) -> EventImpactAnalyzer:
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
    a = EventImpactAnalyzer(sector_mapping_path=str(path))
    # Pre-load impact table
    a.set_impact(_make_impact(EventCategory.EARNINGS_SURPRISE, "Technology", 0.02, 3.0))
    a.set_impact(_make_impact(EventCategory.TARIFF_TRADE, "Energy", 0.015, 5.0))
    a.set_impact(_make_impact(EventCategory.TARIFF_TRADE, "Technology", 0.01, 4.0))
    return a


@pytest.fixture()
def eng(analyzer: EventImpactAnalyzer) -> EventCausalFeatureEngineer:
    return EventCausalFeatureEngineer(impact_analyzer=analyzer)


class TestFeatureNames:
    def test_count(self) -> None:
        assert len(EVENT_CAUSAL_FEATURE_NAMES) == 8

    def test_expected_names(self) -> None:
        expected = {
            "event_impact_score",
            "event_impact_max",
            "event_count_7d",
            "event_sentiment_direction",
            "event_half_life_avg",
            "event_surprise_factor",
            "event_category_dominant",
            "event_decay_phase",
        }
        assert set(EVENT_CAUSAL_FEATURE_NAMES) == expected


class TestImpactScore:
    def test_active_event_produces_impact(
        self, eng: EventCausalFeatureEngineer
    ) -> None:
        """Recent event should produce positive impact score."""
        events = [_make_event(EventCategory.EARNINGS_SURPRISE, "2026-05-28")]
        result = eng.compute(
            sector="Technology",
            current_date="2026-06-01",
            recent_events=events,
            actual_sector_return_5d=0.01,
        )
        assert result["event_impact_score"] > 0

    def test_no_events_returns_zero(self, eng: EventCausalFeatureEngineer) -> None:
        result = eng.compute(
            sector="Technology",
            current_date="2026-06-01",
            recent_events=[],
            actual_sector_return_5d=0.0,
        )
        assert result["event_impact_score"] == 0.0


class TestImpactMax:
    def test_max_picks_strongest(self, eng: EventCausalFeatureEngineer) -> None:
        """With two events, max should be the stronger one."""
        events = [
            _make_event(
                EventCategory.EARNINGS_SURPRISE, "2026-05-31"
            ),  # 1 day ago, magnitude 0.02
            _make_event(
                EventCategory.TARIFF_TRADE, "2026-05-25"
            ),  # 7 days ago, decayed
        ]
        result = eng.compute(
            sector="Technology",
            current_date="2026-06-01",
            recent_events=events,
            actual_sector_return_5d=0.0,
        )
        assert result["event_impact_max"] > 0


class TestEventCount:
    def test_counts_events_in_window(self, eng: EventCausalFeatureEngineer) -> None:
        events = [
            _make_event(EventCategory.EARNINGS_SURPRISE, "2026-05-28"),
            _make_event(EventCategory.TARIFF_TRADE, "2026-05-30"),
            _make_event(EventCategory.EARNINGS_SURPRISE, "2026-05-20"),  # >7d ago
        ]
        result = eng.compute(
            sector="Technology",
            current_date="2026-06-01",
            recent_events=events,
            actual_sector_return_5d=0.0,
        )
        assert result["event_count_7d"] == 2  # only 2 within 7 days


class TestSentimentDirection:
    def test_net_bullish(self, eng: EventCausalFeatureEngineer) -> None:
        events = [
            _make_event(EventCategory.EARNINGS_SURPRISE, "2026-05-30", direction=1),
            _make_event(EventCategory.EARNINGS_SURPRISE, "2026-05-29", direction=1),
        ]
        result = eng.compute(
            sector="Technology",
            current_date="2026-06-01",
            recent_events=events,
            actual_sector_return_5d=0.0,
        )
        assert result["event_sentiment_direction"] > 0


class TestSurpriseFactor:
    def test_positive_surprise(self, eng: EventCausalFeatureEngineer) -> None:
        """Actual return exceeds expected impact → positive surprise."""
        events = [_make_event(EventCategory.EARNINGS_SURPRISE, "2026-05-30")]
        result = eng.compute(
            sector="Technology",
            current_date="2026-06-01",
            recent_events=events,
            actual_sector_return_5d=0.05,  # much bigger than expected ~0.02
        )
        assert result["event_surprise_factor"] > 0


class TestGrangerLeadSignal:
    def test_no_granger_returns_zero(self, eng: EventCausalFeatureEngineer) -> None:
        result = eng.compute(
            sector="Unknown",
            current_date="2026-06-01",
            recent_events=[],
            actual_sector_return_5d=0.0,
        )
        assert result["event_impact_score"] == 0.0


class TestNoImpactData:
    def test_unknown_sector_returns_zeros(
        self, eng: EventCausalFeatureEngineer
    ) -> None:
        events = [_make_event(EventCategory.FDA_APPROVAL, "2026-05-30")]
        result = eng.compute(
            sector="Unknown",
            current_date="2026-06-01",
            recent_events=events,
            actual_sector_return_5d=0.0,
        )
        # No impact data for FDA_APPROVAL in Unknown sector
        assert result["event_impact_score"] == 0.0
