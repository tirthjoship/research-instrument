"""LightGBM predictor implementing StockPredictorPort."""

import json
from pathlib import Path

import lightgbm as lgb
import numpy as np


class LightGBMPredictor:
    """LGBMRegressor wrapper with deterministic feature ordering."""

    def __init__(self, random_seed: int = 42) -> None:
        self._model = lgb.LGBMRegressor(
            n_estimators=200,
            max_depth=6,
            learning_rate=0.05,
            verbosity=-1,
            random_state=random_seed,
        )
        self._feature_names: list[str] = []
        self._booster: lgb.Booster | None = None

    def fit(self, features: list[dict[str, float]], targets: list[float]) -> None:
        self._feature_names = sorted(features[0].keys())
        X = self._to_array(features)
        self._model.fit(X, np.array(targets))
        self._booster = self._model.booster_

    def predict(self, features: list[dict[str, float]]) -> list[float]:
        X = self._to_array(features)
        if self._booster is not None:
            preds = self._booster.predict(X)
        else:
            preds = self._model.predict(X)
        return [float(p) for p in preds]

    def save_model(self, path: str) -> None:
        p = Path(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        if self._booster is not None:
            self._booster.save_model(str(p))
        else:
            self._model.booster_.save_model(str(p))
        meta_path = p.with_suffix(".meta.json")
        meta_path.write_text(json.dumps({"feature_names": self._feature_names}))

    def load_model(self, path: str) -> None:
        p = Path(path)
        self._booster = lgb.Booster(model_file=str(p))
        meta_path = p.with_suffix(".meta.json")
        meta = json.loads(meta_path.read_text())
        self._feature_names = meta["feature_names"]

    def _to_array(self, features: list[dict[str, float]]) -> np.ndarray:
        rows: list[list[float]] = []
        for row in features:
            vals = [row.get(name, float("nan")) for name in self._feature_names]
            rows.append(vals)
        return np.array(rows, dtype=np.float64)
