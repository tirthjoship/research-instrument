"""Ridge regression predictor implementing StockPredictorPort."""

import json
import pickle
from pathlib import Path

import numpy as np
from sklearn.linear_model import Ridge
from sklearn.preprocessing import StandardScaler


class RidgePredictor:
    """Ridge regression with StandardScaler, implementing StockPredictorPort."""

    def __init__(self, alpha: float = 1.0, random_seed: int = 42) -> None:
        self._alpha = alpha
        self._random_seed = random_seed
        self._model = Ridge(alpha=alpha, random_state=random_seed)
        self._scaler = StandardScaler()
        self._feature_names: list[str] = []
        self._train_medians: dict[str, float] = {}

    def fit(self, features: list[dict[str, float]], targets: list[float]) -> None:
        self._feature_names = sorted(features[0].keys())
        X = self._to_array(features)
        # Compute and store column medians for predict-time imputation
        for col_idx, name in enumerate(self._feature_names):
            col = X[:, col_idx]
            median = float(np.nanmedian(col))
            self._train_medians[name] = median if not np.isnan(median) else 0.0
        # Impute training data with computed medians
        X = self._impute_with_medians(X)
        X_scaled = self._scaler.fit_transform(X)
        self._model.fit(X_scaled, np.array(targets))

    def predict(self, features: list[dict[str, float]]) -> list[float]:
        X = self._to_array(features)
        X = self._impute_with_medians(X)
        X_scaled = self._scaler.transform(X)
        preds = self._model.predict(X_scaled)
        return [float(p) for p in preds]

    def save_model(self, path: str) -> None:
        p = Path(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        model_data = {"model": self._model, "scaler": self._scaler}
        with open(str(p), "wb") as f:
            pickle.dump(model_data, f)
        meta_path = p.with_suffix(".meta.json")
        meta_path.write_text(
            json.dumps(
                {
                    "feature_names": self._feature_names,
                    "alpha": self._alpha,
                    "train_medians": self._train_medians,
                }
            )
        )

    def load_model(self, path: str) -> None:
        p = Path(path)
        with open(str(p), "rb") as f:
            model_data = pickle.load(f)  # noqa: S301
        self._model = model_data["model"]
        self._scaler = model_data["scaler"]
        meta_path = p.with_suffix(".meta.json")
        meta = json.loads(meta_path.read_text())
        self._feature_names = meta["feature_names"]
        self._alpha = meta["alpha"]
        self._train_medians = meta.get("train_medians", {})

    def _to_array(self, features: list[dict[str, float]]) -> np.ndarray:
        rows: list[list[float]] = []
        for row in features:
            vals = [row.get(name, float("nan")) for name in self._feature_names]
            rows.append(vals)
        return np.array(rows, dtype=np.float64)

    def _impute_with_medians(self, arr: np.ndarray) -> np.ndarray:
        result = arr.copy()
        for col_idx, name in enumerate(self._feature_names):
            col = result[:, col_idx]
            mask = np.isnan(col)
            if mask.any():
                median = self._train_medians.get(name, 0.0)
                result[mask, col_idx] = median
        return result
