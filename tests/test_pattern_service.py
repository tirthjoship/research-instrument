"""Tests for domain/pattern_service.py — TDD first pass."""

from __future__ import annotations

import pytest

from domain.conviction import ConvictionWeights
from domain.outcome import SignalPerformance, TradeOutcome
from domain.pattern_memory import PatternEntry
from domain.pattern_service import (
    build_patterns_from_outcomes,
    compute_weight_adjustments,
    discover_rules,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _outcome(
    signals: list[str],
    return_pct: float,
    holding_days: int = 5,
    ticker: str = "AAPL",
) -> TradeOutcome:
    return TradeOutcome(
        ticker=ticker,
        buy_trade_id="b1",
        sell_trade_id="s1",
        buy_price=100.0,
        sell_price=100.0 * (1 + return_pct / 100),
        quantity=10,
        buy_date="2026-01-01",
        sell_date="2026-01-06",
        holding_days=holding_days,
        return_pct=return_pct,
        return_dollar=return_pct * 10,
        signals_at_entry=signals,
        conviction_at_entry=7.0,
    )


def _perf(name: str, total: int, wins: int, hit_rate: float) -> SignalPerformance:
    return SignalPerformance(
        signal_name=name,
        total_trades=total,
        winning_trades=wins,
        losing_trades=total - wins,
        hit_rate=hit_rate,
        avg_return_pct=2.0,
    )


def _pattern(
    signals: tuple[str, ...],
    outcome_count: int,
    hit_rate: float,
    avg_return_pct: float,
) -> PatternEntry:
    return PatternEntry(
        signal_combination=signals,
        sector="any",
        market_condition="any",
        outcome_count=outcome_count,
        avg_return_pct=avg_return_pct,
        hit_rate=hit_rate,
        avg_holding_days=5,
    )


# ---------------------------------------------------------------------------
# build_patterns_from_outcomes
# ---------------------------------------------------------------------------


class TestBuildPatterns:
    def test_two_same_signal_combo_groups_correctly(self) -> None:
        outcomes = [
            _outcome(["rsi", "macd"], return_pct=5.0, holding_days=3),
            _outcome(["macd", "rsi"], return_pct=3.0, holding_days=7),
        ]
        patterns = build_patterns_from_outcomes(outcomes)
        assert len(patterns) == 1
        p = patterns[0]
        assert p.outcome_count == 2
        assert p.hit_rate == 1.0  # both profitable
        assert p.avg_return_pct == pytest.approx(4.0)
        assert p.avg_holding_days == 5  # (3+7)//2
        assert p.sector == "any"
        assert p.market_condition == "any"

    def test_empty_outcomes_returns_empty(self) -> None:
        assert build_patterns_from_outcomes([]) == []

    def test_two_distinct_combos_return_two_patterns(self) -> None:
        outcomes = [
            _outcome(["rsi"], return_pct=2.0),
            _outcome(["macd"], return_pct=-1.0),
        ]
        patterns = build_patterns_from_outcomes(outcomes)
        assert len(patterns) == 2

    def test_hit_rate_counts_only_profitable(self) -> None:
        outcomes = [
            _outcome(["vol"], return_pct=3.0),
            _outcome(["vol"], return_pct=-2.0),
            _outcome(["vol"], return_pct=1.0),
        ]
        patterns = build_patterns_from_outcomes(outcomes)
        assert len(patterns) == 1
        assert patterns[0].hit_rate == pytest.approx(2 / 3)

    def test_signal_combination_is_sorted_tuple(self) -> None:
        outcomes = [_outcome(["z_signal", "a_signal"], return_pct=1.0)]
        patterns = build_patterns_from_outcomes(outcomes)
        assert patterns[0].signal_combination == ("a_signal", "z_signal")


# ---------------------------------------------------------------------------
# compute_weight_adjustments
# ---------------------------------------------------------------------------


class TestComputeWeightAdjustments:
    def test_strong_signal_boosted(self) -> None:
        weights = ConvictionWeights()
        perf = _perf("sentiment_momentum", total=20, wins=15, hit_rate=75.0)
        adjustments = compute_weight_adjustments([perf], weights)
        assert len(adjustments) == 1
        adj = adjustments[0]
        assert adj.dimension == "sentiment_momentum"
        assert adj.new_weight > adj.old_weight
        assert adj.new_weight <= 3.0
        assert (
            "boost" in adj.reason.lower()
            or "hit" in adj.reason.lower()
            or adj.direction == "increased"
        )

    def test_weak_signal_reduced(self) -> None:
        weights = ConvictionWeights()
        perf = _perf("ml_direction", total=30, wins=14, hit_rate=46.7)
        adjustments = compute_weight_adjustments([perf], weights)
        assert len(adjustments) == 1
        adj = adjustments[0]
        assert adj.dimension == "ml_direction"
        assert adj.new_weight < adj.old_weight
        assert adj.new_weight >= 0.05

    def test_insufficient_data_no_change(self) -> None:
        weights = ConvictionWeights()
        perf = _perf("smart_money", total=5, wins=4, hit_rate=80.0)
        adjustments = compute_weight_adjustments([perf], weights, min_trades=10)
        assert len(adjustments) == 1
        adj = adjustments[0]
        assert adj.new_weight == adj.old_weight
        assert "insufficient" in adj.reason.lower()

    def test_normal_range_no_change(self) -> None:
        weights = ConvictionWeights()
        perf = _perf("signal_agreement", total=20, wins=11, hit_rate=55.0)
        adjustments = compute_weight_adjustments([perf], weights)
        assert len(adjustments) == 1
        adj = adjustments[0]
        assert adj.new_weight == adj.old_weight
        assert "normal" in adj.reason.lower()

    def test_unknown_signal_skipped(self) -> None:
        weights = ConvictionWeights()
        perf = _perf("unknown_signal_xyz", total=20, wins=18, hit_rate=90.0)
        adjustments = compute_weight_adjustments([perf], weights)
        assert len(adjustments) == 0

    def test_boost_capped_at_max(self) -> None:
        # Start with a weight already at 2.9 — boost should not exceed 3.0
        weights = ConvictionWeights(smart_money=2.9)
        perf = _perf("smart_money", total=20, wins=16, hit_rate=80.0)
        adjustments = compute_weight_adjustments([perf], weights)
        assert adjustments[0].new_weight <= 3.0

    def test_reduction_floored_at_min(self) -> None:
        weights = ConvictionWeights(ml_direction=0.06)
        perf = _perf("ml_direction", total=20, wins=8, hit_rate=40.0)
        adjustments = compute_weight_adjustments([perf], weights)
        assert adjustments[0].new_weight >= 0.05


# ---------------------------------------------------------------------------
# discover_rules
# ---------------------------------------------------------------------------


class TestDiscoverRules:
    def test_bad_pattern_generates_suppress_rule(self) -> None:
        patterns = [
            _pattern(("rsi",), outcome_count=15, hit_rate=0.40, avg_return_pct=1.0)
        ]
        rules = discover_rules(patterns)
        assert len(rules) == 1
        rule = rules[0]
        assert rule.action == "suppress"
        assert 0.0 <= rule.confidence <= 1.0

    def test_strong_pattern_generates_boost_rule(self) -> None:
        patterns = [
            _pattern(
                ("macd", "rsi"), outcome_count=20, hit_rate=0.70, avg_return_pct=4.0
            )
        ]
        rules = discover_rules(patterns)
        assert len(rules) == 1
        rule = rules[0]
        assert rule.action == "boost"
        assert rule.confidence == pytest.approx(min(20 / 20, 1.0))

    def test_unreliable_pattern_no_rules(self) -> None:
        # outcome_count < 10 → is_reliable=False → skip
        patterns = [
            _pattern(("rsi",), outcome_count=5, hit_rate=0.30, avg_return_pct=0.5)
        ]
        rules = discover_rules(patterns)
        assert rules == []

    def test_empty_patterns_returns_empty(self) -> None:
        assert discover_rules([]) == []

    def test_middle_hit_rate_no_rule(self) -> None:
        # 55% hit rate, avg_return 2% — neither suppress nor boost
        patterns = [
            _pattern(("vol",), outcome_count=15, hit_rate=0.55, avg_return_pct=2.0)
        ]
        rules = discover_rules(patterns)
        assert rules == []

    def test_suppress_confidence_formula(self) -> None:
        patterns = [
            _pattern(("rsi",), outcome_count=15, hit_rate=0.35, avg_return_pct=0.0)
        ]
        rules = discover_rules(patterns)
        assert rules[0].confidence == pytest.approx(min(15 / 30, 1.0))

    def test_boost_requires_both_high_hit_and_high_return(self) -> None:
        # High hit rate but avg_return only 2% (< 3%) → no boost
        patterns = [
            _pattern(("rsi",), outcome_count=15, hit_rate=0.70, avg_return_pct=2.0)
        ]
        rules = discover_rules(patterns)
        assert rules == []
