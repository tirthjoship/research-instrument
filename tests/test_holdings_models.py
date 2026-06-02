"""Tests for Holding and SellSignal domain models."""

from __future__ import annotations

import pytest

from domain.models import Holding, SellSignal


class TestHolding:
    def test_valid_creation(self) -> None:
        h = Holding(
            symbol="AMD",
            quantity=50.0,
            purchase_price=165.0,
            purchase_date="2026-05-15",
        )
        assert h.symbol == "AMD"
        assert h.quantity == 50.0
        assert h.purchase_price == 165.0
        assert h.purchase_date == "2026-05-15"
        assert h.notes == ""

    def test_with_notes(self) -> None:
        h = Holding(
            symbol="NVDA",
            quantity=10.0,
            purchase_price=950.0,
            purchase_date="2026-04-01",
            notes="AI play",
        )
        assert h.notes == "AI play"

    def test_is_frozen(self) -> None:
        h = Holding(
            symbol="AMD",
            quantity=50.0,
            purchase_price=165.0,
            purchase_date="2026-05-15",
        )
        with pytest.raises(Exception):
            h.quantity = 100.0  # type: ignore[misc]

    def test_rejects_negative_quantity(self) -> None:
        with pytest.raises(ValueError, match="quantity"):
            Holding(
                symbol="AMD",
                quantity=-1.0,
                purchase_price=165.0,
                purchase_date="2026-05-15",
            )

    def test_rejects_zero_quantity(self) -> None:
        with pytest.raises(ValueError, match="quantity"):
            Holding(
                symbol="AMD",
                quantity=0.0,
                purchase_price=165.0,
                purchase_date="2026-05-15",
            )

    def test_rejects_negative_price(self) -> None:
        with pytest.raises(ValueError, match="purchase_price"):
            Holding(
                symbol="AMD",
                quantity=50.0,
                purchase_price=-10.0,
                purchase_date="2026-05-15",
            )


class TestSellSignal:
    def test_valid_creation(self) -> None:
        s = SellSignal(
            symbol="AMD",
            signal_date="2026-06-01",
            signal_type="crash_risk",
            urgency="immediate",
            reasoning="Negative sentiment spike",
            confidence=0.85,
        )
        assert s.symbol == "AMD"
        assert s.signal_type == "crash_risk"
        assert s.urgency == "immediate"
        assert s.confidence == 0.85

    def test_all_valid_signal_types(self) -> None:
        for st in (
            "crash_risk",
            "negative_sentiment",
            "technical_breakdown",
            "stop_loss",
        ):
            s = SellSignal(
                symbol="X",
                signal_date="2026-01-01",
                signal_type=st,
                urgency="watch",
                reasoning="t",
                confidence=0.5,
            )
            assert s.signal_type == st

    def test_all_valid_urgencies(self) -> None:
        for u in ("immediate", "this_week", "watch"):
            s = SellSignal(
                symbol="X",
                signal_date="2026-01-01",
                signal_type="stop_loss",
                urgency=u,
                reasoning="t",
                confidence=0.5,
            )
            assert s.urgency == u

    def test_rejects_invalid_signal_type(self) -> None:
        with pytest.raises(ValueError, match="signal_type"):
            SellSignal(
                symbol="AMD",
                signal_date="2026-06-01",
                signal_type="invalid",
                urgency="immediate",
                reasoning="test",
                confidence=0.5,
            )

    def test_rejects_invalid_urgency(self) -> None:
        with pytest.raises(ValueError, match="urgency"):
            SellSignal(
                symbol="AMD",
                signal_date="2026-06-01",
                signal_type="crash_risk",
                urgency="invalid",
                reasoning="test",
                confidence=0.5,
            )

    def test_rejects_confidence_above_one(self) -> None:
        with pytest.raises(ValueError, match="confidence"):
            SellSignal(
                symbol="AMD",
                signal_date="2026-06-01",
                signal_type="stop_loss",
                urgency="immediate",
                reasoning="test",
                confidence=1.5,
            )

    def test_rejects_confidence_below_zero(self) -> None:
        with pytest.raises(ValueError, match="confidence"):
            SellSignal(
                symbol="AMD",
                signal_date="2026-06-01",
                signal_type="stop_loss",
                urgency="immediate",
                reasoning="test",
                confidence=-0.1,
            )

    def test_is_frozen(self) -> None:
        s = SellSignal(
            symbol="AMD",
            signal_date="2026-06-01",
            signal_type="stop_loss",
            urgency="immediate",
            reasoning="test",
            confidence=0.9,
        )
        with pytest.raises(Exception):
            s.confidence = 0.1  # type: ignore[misc]
