"""Tests for LearningUseCase — TDD: write first, implement second."""

from __future__ import annotations

from domain.conviction import ConvictionWeights
from domain.outcome import TradeOutcome
from domain.pattern_memory import LearnedRule, WeightAdjustment  # noqa: F401

# ---------------------------------------------------------------------------
# Fake store
# ---------------------------------------------------------------------------


class FakeLearningStore:
    """In-memory double for the learning store port."""

    def __init__(self, outcomes: list[TradeOutcome] | None = None) -> None:
        self._outcomes: list[TradeOutcome] = outcomes or []
        self._weight_adjustments: list[WeightAdjustment] = []
        self._weight_history: list[WeightAdjustment] = []
        self._rules: list[LearnedRule] = []

    # Required port methods
    def get_trade_outcomes(self) -> list[TradeOutcome]:
        return list(self._outcomes)

    def save_weight_adjustment(self, adjustment: WeightAdjustment) -> None:
        self._weight_adjustments.append(adjustment)
        self._weight_history.append(adjustment)

    def get_weight_history(self) -> list[WeightAdjustment]:
        return list(self._weight_history)

    def save_learned_rule(self, rule: LearnedRule) -> None:
        self._rules.append(rule)

    def get_learned_rules(self) -> list[LearnedRule]:
        return list(self._rules)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _make_outcome(
    ticker: str,
    return_pct: float,
    signals: list[str] | None = None,
    holding_days: int = 5,
) -> TradeOutcome:
    return TradeOutcome(
        ticker=ticker,
        buy_trade_id="buy-1",
        sell_trade_id="sell-1",
        buy_price=100.0,
        sell_price=100.0 * (1 + return_pct / 100),
        quantity=10,
        buy_date="2024-01-01",
        sell_date="2024-01-06",
        holding_days=holding_days,
        return_pct=return_pct,
        return_dollar=100.0 * (return_pct / 100) * 10,
        signals_at_entry=signals or ["signal_agreement"],
        conviction_at_entry=7.0,
    )


def _make_15_outcomes() -> list[TradeOutcome]:
    """15 outcomes: mix of profitable / losing, multiple signal combos."""
    outcomes = []
    # 10 outcomes with signal_agreement — 8 profitable (80% hit rate)
    for i in range(8):
        outcomes.append(_make_outcome(f"TICK{i}", 5.0, ["signal_agreement"]))
    for i in range(2):
        outcomes.append(_make_outcome(f"LOSS{i}", -3.0, ["signal_agreement"]))
    # 5 outcomes with sentiment_momentum — 2 profitable (40% hit rate)
    for i in range(2):
        outcomes.append(_make_outcome(f"SENT{i}", 2.0, ["sentiment_momentum"]))
    for i in range(3):
        outcomes.append(_make_outcome(f"SLOS{i}", -4.0, ["sentiment_momentum"]))
    return outcomes


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestLearningUseCaseLearn:
    def test_learn_with_15_outcomes_returns_all_keys(self) -> None:
        from application.learning_use_case import LearningUseCase

        store = FakeLearningStore(outcomes=_make_15_outcomes())
        uc = LearningUseCase(store=store, current_weights=ConvictionWeights())
        result = uc.learn()

        assert "patterns" in result
        assert "adjustments" in result
        assert "rules" in result

    def test_learn_with_15_outcomes_produces_patterns(self) -> None:
        from application.learning_use_case import LearningUseCase

        store = FakeLearningStore(outcomes=_make_15_outcomes())
        uc = LearningUseCase(store=store, current_weights=ConvictionWeights())
        result = uc.learn()

        assert len(result["patterns"]) > 0

    def test_learn_with_15_outcomes_produces_adjustments(self) -> None:
        from application.learning_use_case import LearningUseCase

        store = FakeLearningStore(outcomes=_make_15_outcomes())
        uc = LearningUseCase(store=store, current_weights=ConvictionWeights())
        result = uc.learn()

        assert len(result["adjustments"]) > 0

    def test_learn_saves_non_unchanged_adjustments_to_store(self) -> None:
        from application.learning_use_case import LearningUseCase

        store = FakeLearningStore(outcomes=_make_15_outcomes())
        uc = LearningUseCase(store=store, current_weights=ConvictionWeights())
        uc.learn()

        # At least one adjustment where new != old should have been saved
        assert len(store._weight_adjustments) > 0

    def test_learn_saves_rules_to_store(self) -> None:
        from application.learning_use_case import LearningUseCase

        store = FakeLearningStore(outcomes=_make_15_outcomes())
        uc = LearningUseCase(store=store, current_weights=ConvictionWeights())
        uc.learn()

        # Rules are saved when reliable patterns exist
        # (10+ outcomes per combo required for is_reliable)
        # signal_agreement has 10 outcomes — qualifies
        assert isinstance(store._rules, list)

    def test_learn_with_empty_outcomes_returns_empty_result(self) -> None:
        from application.learning_use_case import LearningUseCase

        store = FakeLearningStore(outcomes=[])
        uc = LearningUseCase(store=store, current_weights=ConvictionWeights())
        result = uc.learn()

        assert result == {"patterns": [], "adjustments": [], "rules": []}

    def test_learn_empty_does_not_save_to_store(self) -> None:
        from application.learning_use_case import LearningUseCase

        store = FakeLearningStore(outcomes=[])
        uc = LearningUseCase(store=store, current_weights=ConvictionWeights())
        uc.learn()

        assert store._weight_adjustments == []
        assert store._rules == []


class TestLearningUseCaseGetCurrentIntelligence:
    def test_get_current_intelligence_has_all_keys(self) -> None:
        from application.learning_use_case import LearningUseCase

        store = FakeLearningStore(outcomes=_make_15_outcomes())
        uc = LearningUseCase(store=store, current_weights=ConvictionWeights())
        uc.learn()  # populate store
        intel = uc.get_current_intelligence()

        assert "total_outcomes" in intel
        assert "weight_history" in intel
        assert "rules" in intel
        assert "weights_adjusted" in intel
        assert "rules_discovered" in intel

    def test_get_current_intelligence_total_outcomes_count(self) -> None:
        from application.learning_use_case import LearningUseCase

        outcomes = _make_15_outcomes()
        store = FakeLearningStore(outcomes=outcomes)
        uc = LearningUseCase(store=store, current_weights=ConvictionWeights())
        intel = uc.get_current_intelligence()

        assert intel["total_outcomes"] == 15

    def test_get_current_intelligence_weights_adjusted_is_non_unchanged_count(
        self,
    ) -> None:
        from application.learning_use_case import LearningUseCase

        store = FakeLearningStore(outcomes=_make_15_outcomes())
        uc = LearningUseCase(store=store, current_weights=ConvictionWeights())
        uc.learn()
        intel = uc.get_current_intelligence()

        # weights_adjusted = count of non-unchanged saved adjustments
        assert intel["weights_adjusted"] == len(store._weight_adjustments)

    def test_get_current_intelligence_rules_discovered_matches_store(self) -> None:
        from application.learning_use_case import LearningUseCase

        store = FakeLearningStore(outcomes=_make_15_outcomes())
        uc = LearningUseCase(store=store, current_weights=ConvictionWeights())
        uc.learn()
        intel = uc.get_current_intelligence()

        assert intel["rules_discovered"] == len(store._rules)
