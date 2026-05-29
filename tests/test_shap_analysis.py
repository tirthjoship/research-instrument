"""Tests for SHAP feature importance analysis."""

import random

import pytest

from application.shap_analysis import compute_shap_importance


def _make_training_data(n_samples=100, n_features=10, seed=42):
    rng = random.Random(seed)
    names = [f"f_{i}" for i in range(n_features)]
    features = [{name: rng.gauss(0, 1) for name in names} for _ in range(n_samples)]
    targets = [sum(f[n] for n in names[:3]) + rng.gauss(0, 0.1) for f in features]
    return features, targets, names


def test_shap_returns_importance_dict() -> None:
    features, targets, names = _make_training_data()
    importance = compute_shap_importance(features, targets, seed=42)
    assert isinstance(importance, dict)
    assert all(name in importance for name in names)
    assert all(isinstance(v, float) for v in importance.values())


def test_shap_top_features_are_signal_features() -> None:
    """Features used to construct target should rank highest."""
    features, targets, names = _make_training_data()
    importance = compute_shap_importance(features, targets, seed=42)
    sorted_feats = sorted(importance.items(), key=lambda x: x[1], reverse=True)
    top_3 = {f for f, _ in sorted_feats[:3]}
    signal_feats = {"f_0", "f_1", "f_2"}
    assert len(top_3 & signal_feats) >= 2
