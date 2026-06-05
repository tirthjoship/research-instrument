"""LearningUseCase — orchestrates pattern analysis, weight adjustment, and rule discovery."""

from __future__ import annotations

from typing import Any

from loguru import logger

from domain.conviction import ConvictionWeights
from domain.outcome import TradeOutcome
from domain.outcome_service import compute_signal_performance
from domain.pattern_memory import LearnedRule, WeightAdjustment
from domain.pattern_service import (
    build_patterns_from_outcomes,
    compute_weight_adjustments,
    discover_rules,
)


class LearningUseCase:
    """Orchestrates pattern analysis, weight adjustment, and rule discovery.

    Args:
        store: Any object implementing get_outcomes, save_weight_adjustment,
               get_weight_history, save_learned_rule, get_learned_rules.
        current_weights: Current ConvictionWeights to adjust from.
    """

    def __init__(self, store: Any, current_weights: ConvictionWeights) -> None:
        self._store = store
        self._current_weights = current_weights

    def learn(self) -> dict[str, Any]:
        """Run the full learning cycle.

        Steps:
        1. Fetch all outcomes.
        2. If empty, return early with empty lists.
        3. Build patterns from outcomes.
        4. Compute signal performance.
        5. Compute weight adjustments.
        6. Save non-unchanged adjustments to store.
        7. Discover rules from patterns.
        8. Save rules to store.
        9. Return patterns, adjustments, rules.

        Returns:
            Dict with keys: patterns, adjustments, rules.
        """
        outcomes: list[TradeOutcome] = self._store.get_trade_outcomes()

        if not outcomes:
            logger.info("LearningUseCase.learn: no outcomes found — skipping")
            return {"patterns": [], "adjustments": [], "rules": []}

        logger.info("LearningUseCase.learn: processing {} outcomes", len(outcomes))

        patterns = build_patterns_from_outcomes(outcomes)
        logger.debug("Built {} patterns", len(patterns))

        performances = compute_signal_performance(outcomes)
        logger.debug("Computed {} signal performances", len(performances))

        adjustments: list[WeightAdjustment] = compute_weight_adjustments(
            performances, self._current_weights
        )

        # Save only adjustments where the weight actually changed
        saved_count = 0
        for adj in adjustments:
            if adj.new_weight != adj.old_weight:
                self._store.save_weight_adjustment(adj)
                saved_count += 1

        logger.info("Saved {} weight adjustments", saved_count)

        rules: list[LearnedRule] = discover_rules(patterns)
        for rule in rules:
            self._store.save_learned_rule(rule)

        logger.info("Discovered and saved {} rules", len(rules))

        return {"patterns": patterns, "adjustments": adjustments, "rules": rules}

    def get_current_intelligence(self) -> dict[str, Any]:
        """Return a summary of the current learning state.

        Returns:
            Dict with keys:
                total_outcomes: int — total outcomes in store.
                weight_history: list[WeightAdjustment] — full adjustment history.
                rules: list[LearnedRule] — all learned rules in store.
                weights_adjusted: int — count of non-unchanged saved adjustments.
                rules_discovered: int — total rules discovered.
        """
        outcomes: list[TradeOutcome] = self._store.get_trade_outcomes()
        weight_history: list[WeightAdjustment] = self._store.get_weight_history()
        rules: list[LearnedRule] = self._store.get_learned_rules()

        return {
            "total_outcomes": len(outcomes),
            "weight_history": weight_history,
            "rules": rules,
            "weights_adjusted": len(weight_history),
            "rules_discovered": len(rules),
        }
