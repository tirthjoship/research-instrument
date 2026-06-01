"""Phase 3B end-to-end validation orchestrator.

Wires: buzz signals -> sentiment features -> Stage 2 training -> ablation -> p-values.
Validates that the complete sentiment pipeline produces real results.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

from loguru import logger

from adapters.ml.keyword_scorer import KeywordScorer
from adapters.ml.sentiment_feature_engineer import SentimentFeatureEngineer
from adapters.ml.stage2_predictor import Stage2Predictor
from application.ablation import AblationRunner
from application.evaluation import PermutationTester
from domain.models import BuzzSignal, Sentiment, SourceReliability


@dataclass
class ValidationReport:
    """Structured report from Phase 3B validation run."""

    timestamp: str
    tickers_evaluated: int
    total_buzz_signals: int
    ablation_results: list[dict[str, object]]
    stage2_trained: bool
    errors: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, object]:
        return {
            "timestamp": self.timestamp,
            "tickers_evaluated": self.tickers_evaluated,
            "total_buzz_signals": self.total_buzz_signals,
            "ablation_results": self.ablation_results,
            "stage2_trained": self.stage2_trained,
            "errors": self.errors,
        }

    def save(self, output_dir: str = "data/reports") -> Path:
        out = Path(output_dir)
        out.mkdir(parents=True, exist_ok=True)
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        path = out / f"phase3b_validation_{ts}.json"
        path.write_text(json.dumps(self.to_dict(), indent=2, default=str))
        logger.info(f"Validation report saved to {path}")
        return path


class Phase3BValidator:
    """Orchestrates end-to-end Phase 3B validation."""

    def __init__(self, random_seed: int = 42, permutation_shuffles: int = 500) -> None:
        self._seed = random_seed
        self._n_shuffles = permutation_shuffles
        self._sfe = SentimentFeatureEngineer()
        self._keyword = KeywordScorer()
        self._perm = PermutationTester(
            n_shuffles=permutation_shuffles, random_seed=random_seed
        )

    def validate(
        self,
        buzz_current: dict[str, list[BuzzSignal]],
        buzz_prior: dict[str, list[BuzzSignal]],
        stage1_predictions: dict[str, list[float]],
        actual_returns: dict[str, list[float]],
    ) -> ValidationReport:
        """Run full validation pipeline."""
        errors: list[str] = []
        all_stage1_preds: list[float] = []
        all_stage2_sentiment_preds: list[float] = []
        all_stage2_full_preds: list[float] = []
        all_actuals: list[float] = []

        tickers_with_buzz = set(buzz_current.keys()) & set(stage1_predictions.keys())
        total_buzz = sum(len(v) for v in buzz_current.values())

        if not tickers_with_buzz:
            logger.warning("No tickers have both buzz data and Stage 1 predictions")
            for ticker, preds in stage1_predictions.items():
                actuals = actual_returns.get(ticker, [])
                n = min(len(preds), len(actuals))
                all_stage1_preds.extend(preds[:n])
                all_stage2_sentiment_preds.extend(preds[:n])
                all_stage2_full_preds.extend(preds[:n])
                all_actuals.extend(actuals[:n])

            ablation = self._run_ablation(
                all_stage1_preds,
                all_stage2_sentiment_preds,
                all_stage2_full_preds,
                all_actuals,
            )
            return ValidationReport(
                timestamp=datetime.now().isoformat(),
                tickers_evaluated=0,
                total_buzz_signals=total_buzz,
                ablation_results=ablation,
                stage2_trained=False,
                errors=["No tickers with both buzz and Stage 1 data"],
            )

        stage2_train_features: list[dict[str, float]] = []
        stage2_train_targets: list[float] = []

        for ticker in tickers_with_buzz:
            try:
                current = buzz_current.get(ticker, [])
                prior = buzz_prior.get(ticker, [])
                preds = stage1_predictions[ticker]
                actuals = actual_returns.get(ticker, [])
                n = min(len(preds), len(actuals))

                kw_scores = [b.sentiment_raw for b in current if b.scorer == "keyword"]
                ft_scores = [b.sentiment_raw for b in current if b.scorer == "flan_t5"]
                kw_avg = sum(kw_scores) / len(kw_scores) if kw_scores else float("nan")
                ft_avg = sum(ft_scores) / len(ft_scores) if ft_scores else float("nan")

                sentiments = [
                    Sentiment(
                        source=b.source,
                        timestamp=b.fetched_at,
                        sentiment_score=b.sentiment_raw,
                        confidence=0.5,
                    )
                    for b in current
                    if b.scorer in ("keyword", "flan_t5")
                ]

                reliability = SourceReliability(
                    source="aggregate", ticker=ticker, correct_calls=0, total_calls=0
                )

                for i in range(n):
                    features = self._sfe.compute(
                        keyword_sentiment=kw_avg,
                        flan_t5_sentiment=ft_avg,
                        sentiments=sentiments,
                        buzz_signals_current=current,
                        buzz_signals_prior=prior,
                        sector_buzz_total=max(len(current), 1),
                        reliability=reliability,
                        price_return_5d=actuals[i] if i < len(actuals) else 0.0,
                    )
                    features["stage1_pred"] = preds[i]
                    stage2_train_features.append(features)
                    stage2_train_targets.append(actuals[i])

                all_stage1_preds.extend(preds[:n])
                all_actuals.extend(actuals[:n])

            except Exception as e:
                errors.append(f"{ticker}: {e}")
                logger.warning(f"Validation error for {ticker}: {e}")
                continue

        stage2_trained = False
        if len(stage2_train_features) >= 10:
            try:
                stage2 = Stage2Predictor(random_seed=self._seed)
                stage2.fit(stage2_train_features, stage2_train_targets)
                stage2_preds = stage2.predict(stage2_train_features)
                all_stage2_sentiment_preds = stage2_preds
                all_stage2_full_preds = stage2_preds
                stage2_trained = True
            except Exception as e:
                errors.append(f"Stage 2 training failed: {e}")
                logger.error(f"Stage 2 training failed: {e}")
                all_stage2_sentiment_preds = list(all_stage1_preds)
                all_stage2_full_preds = list(all_stage1_preds)
        else:
            logger.warning(
                f"Only {len(stage2_train_features)} samples — need 10+ for Stage 2"
            )
            all_stage2_sentiment_preds = list(all_stage1_preds)
            all_stage2_full_preds = list(all_stage1_preds)
            errors.append(
                f"Insufficient data for Stage 2: {len(stage2_train_features)} samples"
            )

        ablation = self._run_ablation(
            all_stage1_preds,
            all_stage2_sentiment_preds,
            all_stage2_full_preds,
            all_actuals,
        )

        return ValidationReport(
            timestamp=datetime.now().isoformat(),
            tickers_evaluated=len(tickers_with_buzz),
            total_buzz_signals=total_buzz,
            ablation_results=ablation,
            stage2_trained=stage2_trained,
            errors=errors,
        )

    def _run_ablation(
        self,
        stage1_preds: list[float],
        stage2_sentiment_preds: list[float],
        stage2_full_preds: list[float],
        actuals: list[float],
    ) -> list[dict[str, object]]:
        """Run three-way ablation + permutation p-values."""
        runner = AblationRunner()
        results = runner.compare(
            stage1_preds, stage2_sentiment_preds, stage2_full_preds, actuals
        )

        pred_lists = [stage1_preds, stage2_sentiment_preds, stage2_full_preds]
        for i, result in enumerate(results):
            if actuals and pred_lists[i]:
                p_value = self._perm.test_directional_accuracy(pred_lists[i], actuals)
                result["p_value"] = p_value
            else:
                result["p_value"] = 1.0

        return results
