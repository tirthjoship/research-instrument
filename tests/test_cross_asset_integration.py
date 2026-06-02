"""Integration test: cross-asset graph → features end-to-end."""

from __future__ import annotations

import math
from datetime import datetime, timedelta

import numpy as np

from adapters.ml.correlation_analyzer import CorrelationAnalyzer
from adapters.ml.cross_asset_features import (
    CROSS_ASSET_FEATURE_NAMES,
    CrossAssetFeatureEngineer,
)
from domain.models import Signal


def _make_signals(symbol: str, prices: list[float]) -> list[Signal]:
    base = datetime(2026, 3, 1)
    return [
        Signal(
            symbol=symbol,
            timestamp=base + timedelta(days=i),
            price=p,
            volume=1_000_000,
            open_=p,
            high=p * 1.01,
            low=p * 0.99,
        )
        for i, p in enumerate(prices)
    ]


def test_end_to_end_graph_to_features(tmp_path) -> None:
    """Build graph from synthetic data, extract features, verify shape."""
    yaml_content = """
relationships:
  - group: test
    leaders: [A]
    followers: [B]
    typical_lag_days: 1
    notes: "test"
"""
    yaml_path = tmp_path / "sc.yaml"
    yaml_path.write_text(yaml_content)

    rng = np.random.default_rng(42)
    prices_a = (100.0 + np.cumsum(rng.normal(0, 0.5, 80))).tolist()
    # B follows A with noise
    prices_b = (100.0 + np.cumsum(rng.normal(0, 0.5, 80))).tolist()

    signals_by_ticker = {
        "A": _make_signals("A", prices_a),
        "B": _make_signals("B", prices_b),
    }

    analyzer = CorrelationAnalyzer(supply_chain_path=str(yaml_path))
    eng = CrossAssetFeatureEngineer(cross_asset=analyzer)

    # Build graph
    analyzer.build_graph(signals_by_ticker, window_days=60)

    # Extract features for B (follower)
    features = eng.compute("B", signals_by_ticker["B"], signals_by_ticker)

    # All 8 features present
    assert set(features.keys()) == set(CROSS_ASSET_FEATURE_NAMES)

    # Supply chain edge should exist → upstream features should not all be NaN
    # (A is leader of B via YAML)
    assert not math.isnan(features["upstream_leader_return_1d"])


def test_no_key_collisions_with_existing_features() -> None:
    """Cross-asset feature names don't overlap with technical/sentiment/fundamental."""
    from adapters.ml.feature_engineer import FeatureEngineer
    from adapters.ml.fundamental_feature_engineer import FUNDAMENTAL_FEATURE_NAMES

    fe = FeatureEngineer()
    technical_names = set(fe.get_feature_names())
    fundamental_names = set(FUNDAMENTAL_FEATURE_NAMES)
    cross_asset_names = set(CROSS_ASSET_FEATURE_NAMES)

    assert technical_names.isdisjoint(
        cross_asset_names
    ), f"Collision: {technical_names & cross_asset_names}"
    assert fundamental_names.isdisjoint(
        cross_asset_names
    ), f"Collision: {fundamental_names & cross_asset_names}"


def test_supply_chain_yaml_loads_all_groups() -> None:
    """Full supply chain YAML loads without error."""
    from pathlib import Path

    import pytest

    yaml_path = Path("config/relationships/supply_chain.yaml")
    if not yaml_path.exists():
        pytest.skip("supply_chain.yaml not found")

    import yaml

    with open(yaml_path) as f:
        data = yaml.safe_load(f)

    groups = data["relationships"]
    assert len(groups) >= 10, f"Expected >= 10 groups, got {len(groups)}"
    for g in groups:
        assert "group" in g
        assert "leaders" in g
        assert "followers" in g
