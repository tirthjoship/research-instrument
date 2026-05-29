"""Ensemble predictor: weighted average of XGBoost + LightGBM + Ridge."""

import json
from pathlib import Path

from adapters.ml.lightgbm_predictor import LightGBMPredictor
from adapters.ml.ridge_predictor import RidgePredictor
from adapters.ml.xgboost_predictor import XGBoostPredictor


class EnsemblePredictor:
    """Weighted ensemble of XGBoost, LightGBM, and Ridge predictors."""

    def __init__(
        self,
        random_seed: int = 42,
        weights: tuple[float, float, float] = (1 / 3, 1 / 3, 1 / 3),
    ) -> None:
        self._xgb = XGBoostPredictor(random_seed=random_seed)
        self._lgbm = LightGBMPredictor(random_seed=random_seed)
        self._ridge = RidgePredictor(random_seed=random_seed)
        self._weights = list(weights)
        self._normalize_weights()

    def fit(self, features: list[dict[str, float]], targets: list[float]) -> None:
        self._xgb.fit(features, targets)
        self._lgbm.fit(features, targets)
        self._ridge.fit(features, targets)

    def predict(self, features: list[dict[str, float]]) -> list[float]:
        preds_xgb = self._xgb.predict(features)
        preds_lgbm = self._lgbm.predict(features)
        preds_ridge = self._ridge.predict(features)

        w = self._weights
        result: list[float] = []
        for px, pl, pr in zip(preds_xgb, preds_lgbm, preds_ridge):
            result.append(w[0] * px + w[1] * pl + w[2] * pr)
        return result

    def predict_with_confidence(
        self, features: list[dict[str, float]]
    ) -> tuple[list[float], list[float]]:
        """Return (weighted_predictions, confidence_scores).

        Confidence = 1 - normalized_std. When all models agree,
        std is 0 and confidence is 1.0. When they disagree maximally,
        confidence approaches 0.
        """
        preds_xgb = self._xgb.predict(features)
        preds_lgbm = self._lgbm.predict(features)
        preds_ridge = self._ridge.predict(features)

        w = self._weights
        result: list[float] = []
        confidences: list[float] = []

        for px, pl, pr in zip(preds_xgb, preds_lgbm, preds_ridge):
            weighted = w[0] * px + w[1] * pl + w[2] * pr
            result.append(weighted)

            std = (
                ((px - weighted) ** 2 + (pl - weighted) ** 2 + (pr - weighted) ** 2) / 3
            ) ** 0.5

            confidence = max(0.0, min(1.0, 1.0 - std / 0.05))
            confidences.append(confidence)

        return result, confidences

    def set_weights(self, weights: tuple[float, float, float]) -> None:
        self._weights = list(weights)
        self._normalize_weights()

    def save_model(self, path: str) -> None:
        p = Path(path)
        p.mkdir(parents=True, exist_ok=True)
        self._xgb.save_model(str(p / "xgboost.model"))
        self._lgbm.save_model(str(p / "lightgbm.model"))
        self._ridge.save_model(str(p / "ridge.model"))
        meta = {"weights": self._weights}
        (p / "ensemble_meta.json").write_text(json.dumps(meta))

    def load_model(self, path: str) -> None:
        p = Path(path)
        self._xgb.load_model(str(p / "xgboost.model"))
        self._lgbm.load_model(str(p / "lightgbm.model"))
        self._ridge.load_model(str(p / "ridge.model"))
        meta = json.loads((p / "ensemble_meta.json").read_text())
        self._weights = meta["weights"]

    def _normalize_weights(self) -> None:
        total = sum(self._weights)
        if total > 0:
            self._weights = [w / total for w in self._weights]
