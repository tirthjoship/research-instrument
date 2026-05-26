"""XGBoost predictor implementing StockPredictorPort."""

import json
from pathlib import Path

import numpy as np
import xgboost as xgb


class XGBoostPredictor:
    """XGBRegressor wrapper with deterministic feature ordering."""

    def __init__(self, random_seed: int = 42) -> None:
        self._model = xgb.XGBRegressor(
            n_estimators=200,
            max_depth=6,
            learning_rate=0.05,
            verbosity=0,
            random_state=random_seed,
        )
        self._feature_names: list[str] = []

    def fit(self, features: list[dict[str, float]], targets: list[float]) -> None:
        self._feature_names = sorted(features[0].keys())
        X = self._to_array(features, impute_value=None)
        self._model.fit(X, np.array(targets))

    def predict(self, features: list[dict[str, float]]) -> list[float]:
        X = self._to_array(features, impute_value=0.0)
        preds = self._model.predict(X)
        return [float(p) for p in preds]

    def save_model(self, path: str) -> None:
        p = Path(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        self._model.save_model(str(p))
        meta_path = p.with_suffix(".meta.json")
        meta_path.write_text(json.dumps({"feature_names": self._feature_names}))

    def load_model(self, path: str) -> None:
        p = Path(path)
        self._model.load_model(str(p))
        meta_path = p.with_suffix(".meta.json")
        meta = json.loads(meta_path.read_text())
        self._feature_names = meta["feature_names"]

    def _to_array(
        self, features: list[dict[str, float]], impute_value: float | None
    ) -> np.ndarray:
        rows: list[list[float]] = []
        for row in features:
            vals = [row.get(name, float("nan")) for name in self._feature_names]
            rows.append(vals)
        arr = np.array(rows, dtype=np.float64)
        if impute_value is None:
            # Impute with column median
            for col_idx in range(arr.shape[1]):
                col = arr[:, col_idx]
                mask = np.isnan(col)
                if mask.any():
                    median = float(np.nanmedian(col))
                    arr[mask, col_idx] = median if not np.isnan(median) else 0.0
        else:
            arr = np.nan_to_num(arr, nan=impute_value)
        return arr
