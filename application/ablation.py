"""Three-way ablation evaluation (grilling decision #2).

Compares:
1. Technical-only (Stage 1 frozen) — Phase 3A baseline
2. Technical + sentiment (Stage 2 without source weights)
3. Technical + sentiment + source weights (Stage 2 full)
"""

from __future__ import annotations

from loguru import logger


class AblationRunner:
    def compare(
        self,
        stage1_preds: list[float],
        stage2_sentiment_preds: list[float],
        stage2_full_preds: list[float],
        actuals: list[float],
    ) -> list[dict[str, object]]:
        return [
            self._evaluate_variant("technical_only", stage1_preds, actuals),
            self._evaluate_variant(
                "technical_plus_sentiment", stage2_sentiment_preds, actuals
            ),
            self._evaluate_variant(
                "technical_plus_sentiment_plus_source_weights",
                stage2_full_preds,
                actuals,
            ),
        ]

    def _evaluate_variant(
        self, variant: str, predictions: list[float], actuals: list[float]
    ) -> dict[str, object]:
        n = len(predictions)
        if n == 0:
            return {
                "variant": variant,
                "directional_accuracy": 0.0,
                "n": 0,
                "correct": 0,
            }
        matches = sum(1 for p, a in zip(predictions, actuals) if (p >= 0) == (a >= 0))
        accuracy = matches / n
        logger.info(f"Ablation [{variant}]: {accuracy:.3f} ({matches}/{n})")
        return {
            "variant": variant,
            "directional_accuracy": accuracy,
            "n": n,
            "correct": matches,
        }

    @staticmethod
    def best_variant(results: list[dict[str, object]]) -> dict[str, object]:
        def _accuracy(r: dict[str, object]) -> float:
            return float(r["directional_accuracy"])  # type: ignore[arg-type]

        return max(results, key=_accuracy)
