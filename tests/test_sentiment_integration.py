"""Integration test: buzz signals -> sentiment features -> Stage 2 -> prediction."""

from datetime import datetime

from adapters.ml.keyword_scorer import KeywordScorer
from adapters.ml.sentiment_feature_engineer import SentimentFeatureEngineer
from adapters.ml.stage2_predictor import Stage2Predictor
from domain.models import BuzzSignal, SourceReliability


class TestSentimentPipelineIntegration:
    def test_full_pipeline_produces_prediction(self):
        """End-to-end: buzz signals -> features -> Stage 2 prediction."""
        buzz_current = [
            BuzzSignal(
                ticker="AAPL",
                source="reuters",
                mention_count=1,
                sentiment_raw=0.6,
                scorer="keyword",
                fetched_at=datetime(2026, 5, 30),
                article_hash=f"k{i}",
            )
            for i in range(8)
        ] + [
            BuzzSignal(
                ticker="AAPL",
                source="reuters",
                mention_count=1,
                sentiment_raw=0.7,
                scorer="flan_t5",
                fetched_at=datetime(2026, 5, 30),
                article_hash=f"f{i}",
            )
            for i in range(8)
        ]
        buzz_prior = [
            BuzzSignal(
                ticker="AAPL",
                source="reuters",
                mention_count=1,
                sentiment_raw=0.3,
                scorer="keyword",
                fetched_at=datetime(2026, 5, 23),
                article_hash=f"p{i}",
            )
            for i in range(3)
        ]

        sfe = SentimentFeatureEngineer()
        features = sfe.compute(
            keyword_sentiment=0.6,
            flan_t5_sentiment=0.7,
            sentiments=[],
            buzz_signals_current=buzz_current,
            buzz_signals_prior=buzz_prior,
            sector_buzz_total=50,
            reliability=SourceReliability(
                source="reuters",
                ticker="AAPL",
                correct_calls=8,
                total_calls=10,
            ),
            price_return_5d=-0.02,
        )
        features["stage1_pred"] = 0.015
        assert (
            len(features) == 25
        )  # 15 original + 10 Phase 3.5 expanded features (Task 6)

        stage2 = Stage2Predictor(random_seed=42)
        train_features = [features] * 50
        train_targets = [0.01] * 25 + [-0.01] * 25
        stage2.fit(train_features, train_targets)
        pred = stage2.predict([features])
        assert len(pred) == 1
        assert isinstance(pred[0], float)

    def test_keyword_scorer_to_features(self):
        """KeywordScorer output feeds correctly into SentimentFeatureEngineer."""
        scorer = KeywordScorer()
        results = scorer.score_text(
            "AAPL",
            "Apple reports record revenue beating expectations, strong growth",
            datetime(2026, 5, 30),
            source="reuters",
        )
        assert len(results) == 1
        assert results[0].sentiment_score > 0

        sfe = SentimentFeatureEngineer()
        features = sfe.compute(
            keyword_sentiment=results[0].sentiment_score,
            flan_t5_sentiment=0.7,
            sentiments=results,
            buzz_signals_current=[],
            buzz_signals_prior=[],
            sector_buzz_total=10,
            reliability=SourceReliability(
                source="reuters",
                ticker="AAPL",
                correct_calls=0,
                total_calls=0,
            ),
            price_return_5d=0.01,
        )
        assert "sentiment_keyword" in features
        assert features["sentiment_keyword"] == results[0].sentiment_score

    def test_ablation_runner_with_real_predictions(self):
        """AblationRunner works with actual prediction lists."""
        from application.ablation import AblationRunner

        runner = AblationRunner()
        results = runner.compare(
            stage1_preds=[0.02, -0.01, 0.03, -0.02],
            stage2_sentiment_preds=[0.03, -0.02, 0.02, -0.01],
            stage2_full_preds=[0.04, -0.03, 0.01, -0.015],
            actuals=[0.01, -0.02, 0.01, -0.03],
        )
        assert len(results) == 3
        for r in results:
            assert 0.0 <= r["directional_accuracy"] <= 1.0
