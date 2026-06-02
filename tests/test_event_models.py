"""Tests for event-causal domain models."""

from __future__ import annotations

import pytest

from domain.models import ClassifiedEvent, EventCategory, EventSectorImpact


class TestEventCategory:
    def test_all_categories_exist(self) -> None:
        expected = {
            "earnings_surprise",
            "tariff_trade",
            "fda_approval",
            "interest_rate",
            "antitrust_regulation",
            "geopolitical",
            "labor_layoffs",
            "supply_chain_disruption",
            "product_launch",
            "macro_data",
        }
        actual = {e.value for e in EventCategory}
        assert actual == expected

    def test_count(self) -> None:
        assert len(EventCategory) == 10


class TestClassifiedEvent:
    def test_valid_creation(self) -> None:
        e = ClassifiedEvent(
            headline="NVDA beats estimates by 20%",
            event_date="2026-05-15",
            category=EventCategory.EARNINGS_SURPRISE,
            direction=1,
            confidence=0.9,
            source="gdelt",
        )
        assert e.category == EventCategory.EARNINGS_SURPRISE
        assert e.direction == 1
        assert e.confidence == 0.9

    def test_is_frozen(self) -> None:
        e = ClassifiedEvent(
            headline="test",
            event_date="2026-01-01",
            category=EventCategory.MACRO_DATA,
            direction=-1,
            confidence=0.5,
            source="gdelt",
        )
        with pytest.raises(Exception):
            e.confidence = 0.1  # type: ignore[misc]

    def test_rejects_invalid_direction(self) -> None:
        with pytest.raises(ValueError, match="direction"):
            ClassifiedEvent(
                headline="test",
                event_date="2026-01-01",
                category=EventCategory.MACRO_DATA,
                direction=2,
                confidence=0.5,
                source="gdelt",
            )

    def test_rejects_confidence_out_of_bounds(self) -> None:
        with pytest.raises(ValueError, match="confidence"):
            ClassifiedEvent(
                headline="test",
                event_date="2026-01-01",
                category=EventCategory.MACRO_DATA,
                direction=1,
                confidence=1.5,
                source="gdelt",
            )

    def test_neutral_direction(self) -> None:
        e = ClassifiedEvent(
            headline="Fed holds rates steady",
            event_date="2026-03-01",
            category=EventCategory.INTEREST_RATE,
            direction=0,
            confidence=0.7,
            source="gdelt",
        )
        assert e.direction == 0


class TestEventSectorImpact:
    def test_valid_creation(self) -> None:
        imp = EventSectorImpact(
            category=EventCategory.TARIFF_TRADE,
            sector="Energy",
            magnitude=0.023,
            half_life_days=4.5,
            sample_count=42,
        )
        assert imp.magnitude == 0.023
        assert imp.half_life_days == 4.5
        assert imp.sample_count == 42

    def test_is_frozen(self) -> None:
        imp = EventSectorImpact(
            category=EventCategory.FDA_APPROVAL,
            sector="Healthcare",
            magnitude=0.035,
            half_life_days=2.0,
            sample_count=15,
        )
        with pytest.raises(Exception):
            imp.magnitude = 0.0  # type: ignore[misc]

    def test_rejects_negative_half_life(self) -> None:
        with pytest.raises(ValueError, match="half_life_days"):
            EventSectorImpact(
                category=EventCategory.MACRO_DATA,
                sector="Financials",
                magnitude=0.01,
                half_life_days=-1.0,
                sample_count=10,
            )

    def test_rejects_negative_sample_count(self) -> None:
        with pytest.raises(ValueError, match="sample_count"):
            EventSectorImpact(
                category=EventCategory.MACRO_DATA,
                sector="Financials",
                magnitude=0.01,
                half_life_days=3.0,
                sample_count=-1,
            )
