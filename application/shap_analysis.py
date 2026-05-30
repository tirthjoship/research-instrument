"""SHAP feature importance analysis for trained models."""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import shap
from loguru import logger

from adapters.ml.xgboost_predictor import XGBoostPredictor


def compute_shap_importance(
    features: list[dict[str, float]],
    targets: list[float],
    seed: int = 42,
    max_samples: int = 500,
) -> dict[str, float]:
    """Train XGBoost and compute mean |SHAP| importance per feature."""
    model = XGBoostPredictor(random_seed=seed)
    model.fit(features, targets)

    feature_names = model._feature_names
    X = model._to_array(features[:max_samples])

    explainer = shap.TreeExplainer(model._model)
    shap_values = explainer.shap_values(X)

    mean_abs = np.mean(np.abs(shap_values), axis=0)

    return {name: float(val) for name, val in zip(feature_names, mean_abs)}


def compute_per_fold_importance(
    folds: list[tuple[list[dict[str, float]], list[float]]],
    seed: int = 42,
    output_path: str | None = None,
) -> dict[str, list[float]]:
    """Compute SHAP importance per fold and track stability."""
    all_importance: dict[str, list[float]] = {}

    for fold_idx, (features, targets) in enumerate(folds):
        if not features:
            continue

        logger.info(f"Computing SHAP for fold {fold_idx + 1}/{len(folds)}")
        importance = compute_shap_importance(features, targets, seed=seed)

        for name, value in importance.items():
            if name not in all_importance:
                all_importance[name] = []
            all_importance[name].append(value)

    if output_path:
        out = Path(output_path)
        out.parent.mkdir(parents=True, exist_ok=True)

        summary: dict[str, dict[str, float]] = {}
        for name, values in all_importance.items():
            summary[name] = {
                "mean": float(np.mean(values)),
                "std": float(np.std(values)),
                "min": float(np.min(values)),
                "max": float(np.max(values)),
                "cv": (
                    float(np.std(values) / np.mean(values))
                    if np.mean(values) > 0
                    else 0.0
                ),
            }

        sorted_summary = dict(
            sorted(summary.items(), key=lambda x: x[1]["mean"], reverse=True)
        )

        out.write_text(json.dumps(sorted_summary, indent=2))
        logger.info(f"SHAP importance saved to {out}")

        for i, (name, stats) in enumerate(sorted_summary.items()):
            if i >= 10:
                break
            logger.info(
                f"  #{i + 1} {name}: mean={stats['mean']:.4f} "
                f"std={stats['std']:.4f} cv={stats['cv']:.2f}"
            )

    return all_importance
