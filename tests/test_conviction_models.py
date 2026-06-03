"""Tests for conviction scoring domain models.

TDD: tests written before implementation.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from domain.conviction import (
    ActionType,
    ConvictionScore,
    ConvictionWeights,
    FreshnessLevel,
    OpportunityCard,
    SmartMoneySignal,
    SmartMoneyType,
)

# ---------------------------------------------------------------------------
# SmartMoneySignal
# ---------------------------------------------------------------------------


class TestSmartMoneySignal:
    def test_valid_13d_creation(self) -> None:
        signal = SmartMoneySignal(
            ticker="AAPL",
            signal_type=SmartMoneyType.FORM_13D,
            filer_name="Berkshire Hathaway",
            stake_pct=5.2,
            transaction_value=1_000_000_000,
            filed_date="2026-06-01",
            is_activist=True,
            source_url="https://sec.gov/cgi-bin/browse-edgar",
        )
        assert signal.ticker == "AAPL"
        assert signal.signal_type == SmartMoneyType.FORM_13D
        assert signal.stake_pct == 5.2
        assert signal.is_activist is True

    def test_form4_with_insider_role(self) -> None:
        signal = SmartMoneySignal(
            ticker="MSFT",
            signal_type=SmartMoneyType.FORM_4,
            filer_name="Satya Nadella",
            stake_pct=None,
            transaction_value=500_000,
            filed_date="2026-05-30",
            is_activist=False,
            insider_role="CEO",
            transaction_type="Purchase",
        )
        assert signal.signal_type == SmartMoneyType.FORM_4
        assert signal.insider_role == "CEO"
        assert signal.transaction_type == "Purchase"
        assert signal.stake_pct is None

    def test_stake_pct_none_allowed(self) -> None:
        signal = SmartMoneySignal(
            ticker="GOOG",
            signal_type=SmartMoneyType.FORM_4,
            filer_name="Sundar Pichai",
            stake_pct=None,
            transaction_value=250_000,
            filed_date="2026-06-01",
            is_activist=False,
        )
        assert signal.stake_pct is None

    def test_stake_pct_zero_allowed(self) -> None:
        signal = SmartMoneySignal(
            ticker="TSLA",
            signal_type=SmartMoneyType.FORM_4,
            filer_name="Some Insider",
            stake_pct=0.0,
            transaction_value=100_000,
            filed_date="2026-06-01",
            is_activist=False,
        )
        assert signal.stake_pct == 0.0

    def test_negative_stake_pct_raises(self) -> None:
        with pytest.raises(ValueError, match="stake_pct"):
            SmartMoneySignal(
                ticker="AAPL",
                signal_type=SmartMoneyType.FORM_13D,
                filer_name="Bad Actor",
                stake_pct=-1.0,
                transaction_value=100_000,
                filed_date="2026-06-01",
                is_activist=False,
            )

    def test_default_optional_fields(self) -> None:
        signal = SmartMoneySignal(
            ticker="NVDA",
            signal_type=SmartMoneyType.FORM_13D,
            filer_name="Some Fund",
            stake_pct=3.1,
            transaction_value=2_000_000,
            filed_date="2026-06-01",
            is_activist=False,
        )
        assert signal.source_url == ""
        assert signal.insider_role == ""
        assert signal.transaction_type == ""

    def test_frozen(self) -> None:
        signal = SmartMoneySignal(
            ticker="AAPL",
            signal_type=SmartMoneyType.FORM_13D,
            filer_name="Berkshire",
            stake_pct=5.0,
            transaction_value=1_000_000,
            filed_date="2026-06-01",
            is_activist=False,
        )
        with pytest.raises((AttributeError, TypeError)):
            signal.ticker = "MSFT"  # type: ignore[misc]


# ---------------------------------------------------------------------------
# ConvictionWeights
# ---------------------------------------------------------------------------


class TestConvictionWeights:
    def test_default_values(self) -> None:
        weights = ConvictionWeights()
        assert weights.signal_agreement == 1.0
        assert weights.smart_money == 1.5
        assert weights.sentiment_momentum == 1.0
        assert weights.fundamental_basis == 1.0
        assert weights.temporal_freshness == 1.2
        assert weights.ml_direction == 0.3

    def test_custom_override(self) -> None:
        weights = ConvictionWeights(smart_money=2.0, ml_direction=0.5)
        assert weights.smart_money == 2.0
        assert weights.ml_direction == 0.5
        # Unchanged defaults
        assert weights.signal_agreement == 1.0

    def test_frozen(self) -> None:
        weights = ConvictionWeights()
        with pytest.raises((AttributeError, TypeError)):
            weights.smart_money = 99.0  # type: ignore[misc]


# ---------------------------------------------------------------------------
# ConvictionScore
# ---------------------------------------------------------------------------


class TestConvictionScore:
    def _make_score(self, score: float = 7.5) -> ConvictionScore:
        return ConvictionScore(
            ticker="AAPL",
            score=score,
            sub_scores={"ml_direction": 0.8, "sentiment": 0.6},
            signals_firing=3,
            freshest_signal=datetime(2026, 6, 3, 10, 0, tzinfo=timezone.utc),
            explanation="Strong buy signal from multiple sources.",
        )

    def test_valid_creation(self) -> None:
        cs = self._make_score(7.5)
        assert cs.ticker == "AAPL"
        assert cs.score == 7.5
        assert cs.signals_firing == 3

    def test_score_at_lower_bound(self) -> None:
        cs = self._make_score(1.0)
        assert cs.score == 1.0

    def test_score_at_upper_bound(self) -> None:
        cs = self._make_score(10.0)
        assert cs.score == 10.0

    def test_score_below_range_raises(self) -> None:
        with pytest.raises(ValueError, match="score"):
            self._make_score(0.9)

    def test_score_above_range_raises(self) -> None:
        with pytest.raises(ValueError, match="score"):
            self._make_score(10.1)

    def test_freshness_level_fresh(self) -> None:
        now = datetime(2026, 6, 3, 12, 0, tzinfo=timezone.utc)
        freshest = now - timedelta(hours=2)  # 2 hours ago → FRESH
        cs = ConvictionScore(
            ticker="AAPL",
            score=5.0,
            sub_scores={},
            signals_firing=1,
            freshest_signal=freshest,
            explanation="test",
        )
        assert cs.freshness_level(now) == FreshnessLevel.FRESH

    def test_freshness_level_recent(self) -> None:
        now = datetime(2026, 6, 3, 12, 0, tzinfo=timezone.utc)
        freshest = now - timedelta(hours=10)  # 10 hours ago → RECENT
        cs = ConvictionScore(
            ticker="AAPL",
            score=5.0,
            sub_scores={},
            signals_firing=1,
            freshest_signal=freshest,
            explanation="test",
        )
        assert cs.freshness_level(now) == FreshnessLevel.RECENT

    def test_freshness_level_stale(self) -> None:
        now = datetime(2026, 6, 3, 12, 0, tzinfo=timezone.utc)
        freshest = now - timedelta(hours=30)  # 30 hours ago → STALE
        cs = ConvictionScore(
            ticker="AAPL",
            score=5.0,
            sub_scores={},
            signals_firing=1,
            freshest_signal=freshest,
            explanation="test",
        )
        assert cs.freshness_level(now) == FreshnessLevel.STALE

    def test_freshness_boundary_fresh_to_recent(self) -> None:
        """Exactly 4 hours → RECENT (not FRESH)."""
        now = datetime(2026, 6, 3, 12, 0, tzinfo=timezone.utc)
        freshest = now - timedelta(hours=4)
        cs = ConvictionScore(
            ticker="AAPL",
            score=5.0,
            sub_scores={},
            signals_firing=1,
            freshest_signal=freshest,
            explanation="test",
        )
        assert cs.freshness_level(now) == FreshnessLevel.RECENT

    def test_freshness_boundary_recent_to_stale(self) -> None:
        """Exactly 24 hours → STALE."""
        now = datetime(2026, 6, 3, 12, 0, tzinfo=timezone.utc)
        freshest = now - timedelta(hours=24)
        cs = ConvictionScore(
            ticker="AAPL",
            score=5.0,
            sub_scores={},
            signals_firing=1,
            freshest_signal=freshest,
            explanation="test",
        )
        assert cs.freshness_level(now) == FreshnessLevel.STALE

    def test_frozen(self) -> None:
        cs = self._make_score()
        with pytest.raises((AttributeError, TypeError)):
            cs.score = 5.0  # type: ignore[misc]


# ---------------------------------------------------------------------------
# OpportunityCard
# ---------------------------------------------------------------------------


class TestOpportunityCard:
    def _make_conviction_score(self) -> ConvictionScore:
        return ConvictionScore(
            ticker="NVDA",
            score=8.5,
            sub_scores={"ml": 0.9, "sentiment": 0.7},
            signals_firing=4,
            freshest_signal=datetime(2026, 6, 3, 8, 0, tzinfo=timezone.utc),
            explanation="Strong AI demand signals.",
        )

    def test_valid_creation(self) -> None:
        cs = self._make_conviction_score()
        card = OpportunityCard(
            ticker="NVDA",
            conviction=8.5,
            action=ActionType.BUY,
            alert_summary="NVDA showing strong institutional accumulation.",
            evidence=[
                "Berkshire filed 13D with 5.2% stake",
                "Google Trends spike +120%",
                "RSI 58 — not overbought",
            ],
            suggestion="Consider initiating a position at current levels.",
            risks=["Valuation stretched vs. peers", "China export restrictions"],
            generated_at=datetime(2026, 6, 3, 12, 0, tzinfo=timezone.utc),
            conviction_score=cs,
        )
        assert card.ticker == "NVDA"
        assert card.action == ActionType.BUY
        assert len(card.evidence) == 3
        assert len(card.risks) == 2
        assert card.conviction_score is cs

    def test_all_action_types(self) -> None:
        cs = self._make_conviction_score()
        for action in ActionType:
            card = OpportunityCard(
                ticker="AAPL",
                conviction=5.0,
                action=action,
                alert_summary="Test",
                evidence=["e1"],
                suggestion="Test suggestion",
                risks=["r1"],
                generated_at=datetime(2026, 6, 3, 12, 0, tzinfo=timezone.utc),
                conviction_score=cs,
            )
            assert card.action == action

    def test_frozen(self) -> None:
        cs = self._make_conviction_score()
        card = OpportunityCard(
            ticker="NVDA",
            conviction=8.5,
            action=ActionType.BUY,
            alert_summary="Test",
            evidence=["e1"],
            suggestion="Test",
            risks=["r1"],
            generated_at=datetime(2026, 6, 3, 12, 0, tzinfo=timezone.utc),
            conviction_score=cs,
        )
        with pytest.raises((AttributeError, TypeError)):
            card.ticker = "MSFT"  # type: ignore[misc]


# ---------------------------------------------------------------------------
# Enum string values
# ---------------------------------------------------------------------------


class TestEnumValues:
    def test_smart_money_type_values(self) -> None:
        assert SmartMoneyType.FORM_13D == "13D"
        assert SmartMoneyType.FORM_4 == "Form4"

    def test_freshness_level_values(self) -> None:
        assert FreshnessLevel.FRESH == "fresh"
        assert FreshnessLevel.RECENT == "recent"
        assert FreshnessLevel.STALE == "stale"

    def test_action_type_members(self) -> None:
        members = {a.name for a in ActionType}
        assert members == {"BUY", "WATCH", "HOLD", "SELL"}
