"""Tests for pattern memory domain models.

TDD: tests written before implementation.
"""

from __future__ import annotations

import pytest

from domain.pattern_memory import LearnedRule, PatternEntry, WeightAdjustment


class TestPatternEntry:
    def test_valid_creation(self) -> None:
        entry = PatternEntry(
            signal_combination=("rsi_oversold", "macd_bullish"),
            sector="Technology",
            market_condition="bull",
            outcome_count=15,
            avg_return_pct=3.5,
            hit_rate=0.67,
            avg_holding_days=5,
        )
        assert entry.sector == "Technology"
        assert entry.outcome_count == 15

    def test_is_reliable_true(self) -> None:
        entry = PatternEntry(
            signal_combination=("rsi_oversold",),
            sector="Energy",
            market_condition="bear",
            outcome_count=10,
            avg_return_pct=1.2,
            hit_rate=0.55,
            avg_holding_days=3,
        )
        assert entry.is_reliable is True

    def test_is_reliable_false(self) -> None:
        entry = PatternEntry(
            signal_combination=("rsi_oversold",),
            sector="Energy",
            market_condition="bear",
            outcome_count=9,
            avg_return_pct=1.2,
            hit_rate=0.55,
            avg_holding_days=3,
        )
        assert entry.is_reliable is False

    def test_pattern_key_format(self) -> None:
        entry = PatternEntry(
            signal_combination=("macd_bullish", "rsi_oversold"),
            sector="Technology",
            market_condition="bull",
            outcome_count=12,
            avg_return_pct=2.0,
            hit_rate=0.6,
            avg_holding_days=4,
        )
        # signals sorted alphabetically
        assert entry.pattern_key == "macd_bullish+rsi_oversold|Technology|bull"

    def test_pattern_key_single_signal(self) -> None:
        entry = PatternEntry(
            signal_combination=("volume_spike",),
            sector="Financials",
            market_condition="neutral",
            outcome_count=5,
            avg_return_pct=0.5,
            hit_rate=0.4,
            avg_holding_days=2,
        )
        assert entry.pattern_key == "volume_spike|Financials|neutral"

    def test_frozen(self) -> None:
        entry = PatternEntry(
            signal_combination=("rsi_oversold",),
            sector="Energy",
            market_condition="bear",
            outcome_count=5,
            avg_return_pct=1.0,
            hit_rate=0.5,
            avg_holding_days=3,
        )
        with pytest.raises((AttributeError, TypeError)):
            entry.outcome_count = 99  # type: ignore[misc]


class TestWeightAdjustment:
    def test_direction_increased(self) -> None:
        adj = WeightAdjustment(
            dimension="sentiment_momentum",
            old_weight=1.0,
            new_weight=1.3,
            reason="Sentiment outperforming",
            adjusted_date="2026-06-03",
        )
        assert adj.direction == "increased"

    def test_direction_decreased(self) -> None:
        adj = WeightAdjustment(
            dimension="ml_direction",
            old_weight=0.5,
            new_weight=0.3,
            reason="ML underperforming",
            adjusted_date="2026-06-03",
        )
        assert adj.direction == "decreased"

    def test_direction_unchanged(self) -> None:
        adj = WeightAdjustment(
            dimension="fundamental_basis",
            old_weight=1.0,
            new_weight=1.0,
            reason="No change needed",
            adjusted_date="2026-06-03",
        )
        assert adj.direction == "unchanged"

    def test_change_calculation(self) -> None:
        adj = WeightAdjustment(
            dimension="smart_money",
            old_weight=1.5,
            new_weight=1.8,
            reason="Strong insider activity",
            adjusted_date="2026-06-03",
        )
        assert adj.change == 0.3

    def test_change_negative(self) -> None:
        adj = WeightAdjustment(
            dimension="smart_money",
            old_weight=1.5,
            new_weight=1.2,
            reason="Insider selling",
            adjusted_date="2026-06-03",
        )
        assert adj.change == -0.3

    def test_frozen(self) -> None:
        adj = WeightAdjustment(
            dimension="ml_direction",
            old_weight=0.3,
            new_weight=0.5,
            reason="test",
            adjusted_date="2026-06-03",
        )
        with pytest.raises((AttributeError, TypeError)):
            adj.new_weight = 9.9  # type: ignore[misc]


class TestLearnedRule:
    def test_valid_creation(self) -> None:
        rule = LearnedRule(
            rule_id="rule_001",
            description="Suppress RSI in bear markets",
            signal_combination=("rsi_oversold",),
            sector="Technology",
            action="suppress",
            confidence=0.8,
            supporting_outcomes=25,
            learned_date="2026-06-03",
        )
        assert rule.rule_id == "rule_001"
        assert rule.action == "suppress"

    def test_is_high_confidence_true(self) -> None:
        rule = LearnedRule(
            rule_id="rule_002",
            description="Boost MACD in tech bull runs",
            signal_combination=("macd_bullish",),
            sector="Technology",
            action="boost",
            confidence=0.7,
            supporting_outcomes=30,
            learned_date="2026-06-03",
        )
        assert rule.is_high_confidence is True

    def test_is_high_confidence_false(self) -> None:
        rule = LearnedRule(
            rule_id="rule_003",
            description="Warn on volume spikes",
            signal_combination=("volume_spike",),
            sector="Energy",
            action="warn",
            confidence=0.69,
            supporting_outcomes=10,
            learned_date="2026-06-03",
        )
        assert rule.is_high_confidence is False

    def test_frozen(self) -> None:
        rule = LearnedRule(
            rule_id="rule_004",
            description="test",
            signal_combination=("rsi_oversold",),
            sector="Financials",
            action="suppress",
            confidence=0.5,
            supporting_outcomes=5,
            learned_date="2026-06-03",
        )
        with pytest.raises((AttributeError, TypeError)):
            rule.confidence = 0.99  # type: ignore[misc]
