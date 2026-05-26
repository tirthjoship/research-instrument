"""Tests for ML predictors."""

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
            assert lo <= preds_ens[i] <= hi, (
                f"Ensemble pred {preds_ens[i]} outside [{lo}, {hi}] at index {i}"
            )

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
