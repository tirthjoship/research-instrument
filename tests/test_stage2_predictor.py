"""Tests for Stage2Predictor — XGBoost stacking model blending Stage 1 + sentiment."""

import math
import os
import tempfile

from adapters.ml.stage2_predictor import STAGE2_FEATURE_NAMES, Stage2Predictor


def _make_features(n: int = 50) -> list[dict[str, float]]:
    return [
        {
            "stage1_pred": 0.02,
            "buzz_volume": 10,
            "sentiment_keyword": 0.5,
            "sentiment_flan_t5": 0.6,
            "sentiment_agreement": 1.0,
            "buzz_acceleration": 2.0,
            "sentiment_momentum_3d": 0.1,
            "sentiment_momentum_7d": 0.05,
            "source_weighted_sentiment": 0.4,
            "top_source_reliability": 0.8,
            "rss_reddit_divergence": 0.0,
            "sentiment_price_divergence_flag": 1.0,
            "sentiment_price_divergence_magnitude": 0.04,
            "buzz_price_divergence": 0.0,
            "sector_buzz_ratio": 0.2,
        }
    ] * n


def test_fit_and_predict() -> None:
    predictor = Stage2Predictor()
    features = _make_features(50)
    targets = [float(i % 10) * 0.01 for i in range(50)]
    predictor.fit(features, targets)

    preds = predictor.predict(_make_features(5))
    assert len(preds) == 5
    for p in preds:
        assert not math.isnan(p), f"Expected non-NaN prediction, got {p}"


def test_predict_with_confidence() -> None:
    predictor = Stage2Predictor()
    features = _make_features(50)
    targets = [float(i % 10) * 0.01 for i in range(50)]
    predictor.fit(features, targets)

    preds, confidences = predictor.predict_with_confidence(_make_features(5))
    assert len(preds) == 5
    assert len(confidences) == 5
    for c in confidences:
        assert 0.0 <= c <= 1.0, f"Confidence {c} out of [0, 1]"


def test_save_and_load() -> None:
    predictor = Stage2Predictor()
    features = _make_features(50)
    targets = [float(i % 10) * 0.01 for i in range(50)]
    predictor.fit(features, targets)
    original_preds = predictor.predict(_make_features(5))

    with tempfile.TemporaryDirectory() as tmpdir:
        model_path = os.path.join(tmpdir, "stage2.ubj")
        predictor.save_model(model_path)

        loaded = Stage2Predictor()
        loaded.load_model(model_path)
        loaded_preds = loaded.predict(_make_features(5))

    assert len(original_preds) == len(loaded_preds)
    for orig, loaded_p in zip(original_preds, loaded_preds):
        assert abs(orig - loaded_p) < 1e-6, f"Mismatch: {orig} vs {loaded_p}"


def test_feature_names_include_stage1_and_sentiment() -> None:
    predictor = Stage2Predictor()
    names = predictor.get_feature_names()

    assert "stage1_pred" in names, "stage1_pred must be in feature names"
    assert (
        len(names) == 25
    ), f"Expected 25 features, got {len(names)}"  # 15 original + 10 Phase 3.5 expanded (Task 6)
    assert names == STAGE2_FEATURE_NAMES
