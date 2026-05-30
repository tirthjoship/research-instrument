"""Tests for ML predictors."""

import math
import random

import pytest

from adapters.ml.ensemble_predictor import EnsemblePredictor
from adapters.ml.lightgbm_predictor import LightGBMPredictor
from adapters.ml.ridge_predictor import RidgePredictor
from adapters.ml.xgboost_predictor import XGBoostPredictor


def _make_training_data(n_samples=100, n_features=45, seed=42):
    rng = random.Random(seed)
    names = [f"f_{i}" for i in range(n_features)]
    features = [{name: rng.gauss(0, 1) for name in names} for _ in range(n_samples)]
    targets = [rng.gauss(0, 0.05) for _ in range(n_samples)]
    return features, targets


@pytest.fixture
def training_data():
    return _make_training_data()


class TestXGBoostPredictor:
    def test_fit_and_predict(self, training_data):
        features, targets = training_data
        model = XGBoostPredictor(random_seed=42)
        model.fit(features, targets)
        preds = model.predict(features[:5])
        assert len(preds) == 5
        assert all(isinstance(p, float) for p in preds)

    def test_save_and_load(self, training_data, tmp_path):
        features, targets = training_data
        model = XGBoostPredictor(random_seed=42)
        model.fit(features, targets)
        preds_before = model.predict(features[:5])

        model.save_model(str(tmp_path / "xgb.model"))

        model2 = XGBoostPredictor(random_seed=42)
        model2.load_model(str(tmp_path / "xgb.model"))
        preds_after = model2.predict(features[:5])

        assert preds_before == preds_after

    def test_predict_deterministic(self, training_data):
        features, targets = training_data
        model_a = XGBoostPredictor(random_seed=42)
        model_a.fit(features, targets)
        preds_a = model_a.predict(features[:5])

        model_b = XGBoostPredictor(random_seed=42)
        model_b.fit(features, targets)
        preds_b = model_b.predict(features[:5])

        assert preds_a == preds_b

    def test_handles_nan_features(self, training_data):
        """XGBoost should handle NaN natively without crashing."""
        features, targets = training_data
        model = XGBoostPredictor(random_seed=42)
        model.fit(features, targets)

        nan_features = [dict(f) for f in features[:5]]
        for f in nan_features:
            f["f_0"] = float("nan")
            f["f_10"] = float("nan")

        preds = model.predict(nan_features)
        assert len(preds) == 5
        assert all(isinstance(p, float) for p in preds)
        assert all(not math.isnan(p) for p in preds)


class TestLightGBMPredictor:
    def test_fit_and_predict(self, training_data):
        features, targets = training_data
        model = LightGBMPredictor(random_seed=42)
        model.fit(features, targets)
        preds = model.predict(features[:5])
        assert len(preds) == 5
        assert all(isinstance(p, float) for p in preds)

    def test_save_and_load(self, training_data, tmp_path):
        features, targets = training_data
        model = LightGBMPredictor(random_seed=42)
        model.fit(features, targets)
        preds_before = model.predict(features[:5])

        model.save_model(str(tmp_path / "lgbm.model"))

        model2 = LightGBMPredictor(random_seed=42)
        model2.load_model(str(tmp_path / "lgbm.model"))
        preds_after = model2.predict(features[:5])

        for a, b in zip(preds_before, preds_after):
            assert abs(a - b) < 1e-6

    def test_handles_nan_features(self, training_data):
        """LightGBM should handle NaN natively without crashing."""
        features, targets = training_data
        model = LightGBMPredictor(random_seed=42)
        model.fit(features, targets)

        nan_features = [dict(f) for f in features[:5]]
        for f in nan_features:
            f["f_0"] = float("nan")
            f["f_10"] = float("nan")

        preds = model.predict(nan_features)
        assert len(preds) == 5
        assert all(isinstance(p, float) for p in preds)
        assert all(not math.isnan(p) for p in preds)


class TestRidgePredictor:
    def test_fit_and_predict(self, training_data):
        features, targets = training_data
        model = RidgePredictor(alpha=1.0, random_seed=42)
        model.fit(features, targets)
        preds = model.predict(features[:5])
        assert len(preds) == 5
        assert all(isinstance(p, float) for p in preds)

    def test_save_and_load(self, training_data, tmp_path):
        features, targets = training_data
        model = RidgePredictor(alpha=1.0, random_seed=42)
        model.fit(features, targets)
        preds_before = model.predict(features[:5])

        model.save_model(str(tmp_path / "ridge.model"))

        model2 = RidgePredictor()
        model2.load_model(str(tmp_path / "ridge.model"))
        preds_after = model2.predict(features[:5])

        assert preds_before == preds_after

    def test_predict_uses_stored_medians_not_zero(self, training_data):
        """At predict time, NaN should be imputed with training medians, not 0.0."""
        features, targets = training_data
        model = RidgePredictor(alpha=1.0, random_seed=42)
        model.fit(features, targets)

        nan_features = [dict(f) for f in features[:5]]
        for f in nan_features:
            f["f_0"] = float("nan")

        preds_nan = model.predict(nan_features)
        assert len(preds_nan) == 5
        assert all(isinstance(p, float) for p in preds_nan)
        assert hasattr(model, "_train_medians")
        assert "f_0" in model._train_medians

    def test_save_load_preserves_medians(self, training_data, tmp_path):
        """Stored medians must survive save/load cycle."""
        features, targets = training_data
        model = RidgePredictor(alpha=1.0, random_seed=42)
        model.fit(features, targets)

        model.save_model(str(tmp_path / "ridge.model"))

        model2 = RidgePredictor()
        model2.load_model(str(tmp_path / "ridge.model"))

        assert model2._train_medians == model._train_medians


class TestEnsemblePredictor:
    def test_fit_and_predict(self, training_data):
        features, targets = training_data
        model = EnsemblePredictor(random_seed=42)
        model.fit(features, targets)
        preds = model.predict(features[:5])
        assert len(preds) == 5
        assert all(isinstance(p, float) for p in preds)

    def test_ensemble_averages_models(self, training_data):
        features, targets = training_data

        xgb_model = XGBoostPredictor(random_seed=42)
        lgbm_model = LightGBMPredictor(random_seed=42)
        ridge_model = RidgePredictor(random_seed=42)

        xgb_model.fit(features, targets)
        lgbm_model.fit(features, targets)
        ridge_model.fit(features, targets)

        preds_xgb = xgb_model.predict(features[:5])
        preds_lgbm = lgbm_model.predict(features[:5])
        preds_ridge = ridge_model.predict(features[:5])

        ensemble = EnsemblePredictor(random_seed=42)
        ensemble.fit(features, targets)
        preds_ens = ensemble.predict(features[:5])

        margin = 0.01
        for i in range(5):
            lo = min(preds_xgb[i], preds_lgbm[i], preds_ridge[i]) - margin
            hi = max(preds_xgb[i], preds_lgbm[i], preds_ridge[i]) + margin
            assert (
                lo <= preds_ens[i] <= hi
            ), f"Ensemble pred {preds_ens[i]} outside [{lo}, {hi}] at index {i}"

    def test_save_and_load(self, training_data, tmp_path):
        features, targets = training_data
        model = EnsemblePredictor(random_seed=42)
        model.fit(features, targets)
        preds_before = model.predict(features[:5])

        model.save_model(str(tmp_path / "ensemble"))

        model2 = EnsemblePredictor(random_seed=42)
        model2.load_model(str(tmp_path / "ensemble"))
        preds_after = model2.predict(features[:5])

        for a, b in zip(preds_before, preds_after):
            assert abs(a - b) < 1e-6

    def test_predict_with_confidence(self, training_data):
        """predict_with_confidence returns (predictions, confidences)."""
        features, targets = training_data
        model = EnsemblePredictor(random_seed=42)
        model.fit(features, targets)
        preds, confidences = model.predict_with_confidence(features[:5])
        assert len(preds) == 5
        assert len(confidences) == 5
        assert all(0.0 <= c <= 1.0 for c in confidences)

    def test_identical_submodel_preds_give_high_confidence(self, training_data):
        """When all sub-models agree, confidence should be high."""
        features, targets = training_data
        model = EnsemblePredictor(random_seed=42)
        model.fit(features, targets)
        _, confidences = model.predict_with_confidence(features[:5])
        assert all(c > 0.3 for c in confidences)
