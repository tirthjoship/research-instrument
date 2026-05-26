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

    def fit(self, features: list[dict[str, float]], targets: list[float]) -> None:
        self._feature_names = sorted(features[0].keys())
        X = self._to_array(features, impute_value=None)
        X_scaled = self._scaler.fit_transform(X)
        self._model.fit(X_scaled, np.array(targets))

    def predict(self, features: list[dict[str, float]]) -> list[float]:
        X = self._to_array(features, impute_value=0.0)
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
            json.dumps({"feature_names": self._feature_names, "alpha": self._alpha})
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

    def _to_array(
        self, features: list[dict[str, float]], impute_value: float | None
    ) -> np.ndarray:
        rows: list[list[float]] = []
        for row in features:
            vals = [row.get(name, float("nan")) for name in self._feature_names]
            rows.append(vals)
        arr = np.array(rows, dtype=np.float64)
        if impute_value is None:
            for col_idx in range(arr.shape[1]):
                col = arr[:, col_idx]
                mask = np.isnan(col)
                if mask.any():
                    median = float(np.nanmedian(col))
                    arr[mask, col_idx] = median if not np.isnan(median) else 0.0
        else:
            arr = np.nan_to_num(arr, nan=impute_value)
        return arr
