"""Integration test: event classification → impact learning → features."""

from __future__ import annotations

import pytest

from adapters.ml.event_causal_features import (
    EVENT_CAUSAL_FEATURE_NAMES,
    EventCausalFeatureEngineer,
)
from adapters.ml.event_impact_analyzer import EventImpactAnalyzer
from domain.models import ClassifiedEvent, EventCategory


def test_end_to_end_impact_to_features(tmp_path) -> None:
    """Learn impact from events, then extract features."""
    content = """
mappings:
  earnings_surprise:
    - sector: Technology
      direction: 1
"""
    path = tmp_path / "mapping.yaml"
    path.write_text(content)

    analyzer = EventImpactAnalyzer(sector_mapping_path=str(path))

    # Learn impact from historical events
    events = [
        ClassifiedEvent(
            "NVDA beats",
            f"2025-0{i+1}-15",
            EventCategory.EARNINGS_SURPRISE,
            1,
            0.9,
            "test",
        )
        for i in range(5)
    ]
    returns = {
        f"2025-0{i+1}-15": [0.02, 0.015, 0.01, 0.005, 0.002, 0.001, 0.0, 0.0, 0.0, 0.0]
        for i in range(5)
    }
    impact = analyzer.learn_impact(events, "Technology", returns)
    assert impact is not None
    assert impact.magnitude > 0

    # Extract features using learned impact
    eng = EventCausalFeatureEngineer(impact_analyzer=analyzer)
    recent = [
        ClassifiedEvent(
            "AMD beats", "2026-05-30", EventCategory.EARNINGS_SURPRISE, 1, 0.85, "test"
        )
    ]
    features = eng.compute(
        sector="Technology",
        current_date="2026-06-01",
        recent_events=recent,
        actual_sector_return_5d=0.03,
    )
    assert set(features.keys()) == set(EVENT_CAUSAL_FEATURE_NAMES)
    assert features["event_impact_score"] > 0
    assert features["event_count_7d"] == 1
    assert features["event_surprise_factor"] != 0.0


def test_no_key_collisions_with_existing_features() -> None:
    """Event feature names don't overlap with other feature layers."""
    from adapters.ml.cross_asset_features import CROSS_ASSET_FEATURE_NAMES
    from adapters.ml.feature_engineer import FeatureEngineer
    from adapters.ml.fundamental_feature_engineer import FUNDAMENTAL_FEATURE_NAMES

    fe = FeatureEngineer()
    technical = set(fe.get_feature_names())
    fundamental = set(FUNDAMENTAL_FEATURE_NAMES)
    cross_asset = set(CROSS_ASSET_FEATURE_NAMES)
    event_causal = set(EVENT_CAUSAL_FEATURE_NAMES)

    assert technical.isdisjoint(event_causal), f"Collision: {technical & event_causal}"
    assert fundamental.isdisjoint(
        event_causal
    ), f"Collision: {fundamental & event_causal}"
    assert cross_asset.isdisjoint(
        event_causal
    ), f"Collision: {cross_asset & event_causal}"


def test_sector_mapping_yaml_loads() -> None:
    """Full sector mapping YAML loads without error."""
    from pathlib import Path

    import yaml

    yaml_path = Path("config/events/sector_mapping.yaml")
    if not yaml_path.exists():
        pytest.skip("sector_mapping.yaml not found")

    with open(yaml_path) as f:
        data = yaml.safe_load(f)

    mappings = data["mappings"]
    assert len(mappings) >= 10, f"Expected >= 10 categories, got {len(mappings)}"
