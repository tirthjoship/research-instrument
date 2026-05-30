"""Stage 2 stacking predictor — XGBoost blending Stage 1 output with sentiment features.

ADR-014: Two-stage stacking architecture.
Stage 2 takes stage1_pred (technical model output) + 14 sentiment features as inputs.
"""

import json
from pathlib import Path

import numpy as np
import xgboost as xgb

from adapters.ml.sentiment_feature_engineer import SENTIMENT_FEATURE_NAMES

STAGE2_FEATURE_NAMES: list[str] = ["stage1_pred"] + list(SENTIMENT_FEATURE_NAMES)


class Stage2Predictor:
    """XGBoost stacking model combining Stage 1 predictions with sentiment features."""

    def __init__(self, random_seed: int = 42) -> None:
        self._model = xgb.XGBRegressor(
            n_estimators=100,
            max_depth=4,
            learning_rate=0.05,
            subsample=0.8,
            colsample_bytree=0.8,
            random_state=random_seed,
            verbosity=0,
        )
        self._feature_names: list[str] = list(STAGE2_FEATURE_NAMES)
        self._is_fitted: bool = False

    def get_feature_names(self) -> list[str]:
        """Return ordered feature names for Stage 2."""
        return list(self._feature_names)

    def fit(self, features: list[dict[str, float]], targets: list[float]) -> None:
        """Fit the Stage 2 model.

        Args:
            features: List of feature dicts; must include stage1_pred + sentiment keys.
            targets: Continuous target values (e.g., 5-day forward returns).
        """
        X = self._to_array(features)
        self._model.fit(X, np.array(targets))
        self._is_fitted = True

    def predict(self, features: list[dict[str, float]]) -> list[float]:
        """Generate Stage 2 predictions.

        Args:
            features: List of feature dicts for inference.

        Returns:
            List of float predictions.
        """
        X = self._to_array(features)
        preds = self._model.predict(X)
        return [float(p) for p in preds]

    def predict_with_confidence(
        self, features: list[dict[str, float]]
    ) -> tuple[list[float], list[float]]:
        """Generate predictions with confidence scores in [0, 1].

        Confidence is derived from the absolute prediction value clipped and
        scaled relative to a reasonable return magnitude (5% = max confidence).

        Args:
            features: List of feature dicts for inference.

        Returns:
            Tuple of (predictions, confidences) where each confidence is in [0, 1].
        """
        preds = self.predict(features)
        # Scale |pred| to [0, 1]; clip at 5% absolute return for max confidence
        max_return = 0.05
        confidences = [min(abs(p) / max_return, 1.0) for p in preds]
        return preds, confidences

    def save_model(self, path: str) -> None:
        """Save XGBoost model and feature metadata to disk.

        Args:
            path: File path for the model (e.g., stage2.ubj). A companion
                  .meta.json is written alongside.
        """
        p = Path(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        self._model.save_model(str(p))
        meta_path = p.with_suffix(".meta.json")
        meta_path.write_text(
            json.dumps(
                {"feature_names": self._feature_names, "is_fitted": self._is_fitted}
            )
        )

    def load_model(self, path: str) -> None:
        """Load XGBoost model and feature metadata from disk.

        Args:
            path: File path of the saved model (same path used in save_model).
        """
        p = Path(path)
        self._model.load_model(str(p))
        meta_path = p.with_suffix(".meta.json")
        meta = json.loads(meta_path.read_text())
        self._feature_names = meta["feature_names"]
        self._is_fitted = meta.get("is_fitted", True)

    def _to_array(self, features: list[dict[str, float]]) -> np.ndarray:
        """Convert list of feature dicts to numpy array using fixed feature order.

        Missing keys are filled with float("nan").
        """
        rows: list[list[float]] = []
        for row in features:
            vals = [row.get(name, float("nan")) for name in self._feature_names]
            rows.append(vals)
        return np.array(rows, dtype=np.float64)
