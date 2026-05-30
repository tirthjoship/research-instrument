"""Tests for three-way ablation runner."""

from __future__ import annotations

import pytest

from application.ablation import AblationRunner


@pytest.fixture
def runner() -> AblationRunner:
    return AblationRunner()


def test_technical_only_uses_stage1(runner: AblationRunner) -> None:
    """Stage 1 predictions that all match actuals should yield directional_accuracy=1.0."""
    stage1_preds = [0.1, 0.2, 0.3]
    stage2_sentiment_preds = [0.1, 0.2, 0.3]
    stage2_full_preds = [0.1, 0.2, 0.3]
    actuals = [0.5, 1.0, 0.7]  # all positive — all match

    results = runner.compare(
        stage1_preds, stage2_sentiment_preds, stage2_full_preds, actuals
    )

    technical_only = next(r for r in results if r["variant"] == "technical_only")
    assert technical_only["directional_accuracy"] == 1.0
    assert technical_only["n"] == 3
    assert technical_only["correct"] == 3


def test_three_variants_returned(runner: AblationRunner) -> None:
    """compare() must return exactly 3 results with the expected variant names."""
    preds = [0.1, -0.2, 0.3]
    actuals = [0.5, -0.1, 0.2]

    results = runner.compare(preds, preds, preds, actuals)

    assert len(results) == 3
    variant_names = {r["variant"] for r in results}
    assert variant_names == {
        "technical_only",
        "technical_plus_sentiment",
        "technical_plus_sentiment_plus_source_weights",
    }


def test_identifies_best_variant(runner: AblationRunner) -> None:
    """best_variant() returns the variant with highest directional_accuracy."""
    actuals = [0.1, 0.2, -0.3]

    # technical_only: all match → 1.0
    stage1_preds = [0.5, 0.5, -0.5]
    # technical_plus_sentiment: 2/3 match → ~0.667
    stage2_sentiment_preds = [0.5, 0.5, 0.5]
    # technical_plus_sentiment_plus_source_weights: 1/3 match → ~0.333
    stage2_full_preds = [-0.5, -0.5, -0.5]

    results = runner.compare(
        stage1_preds, stage2_sentiment_preds, stage2_full_preds, actuals
    )
    best = AblationRunner.best_variant(results)

    assert best["variant"] == "technical_only"
    assert best["directional_accuracy"] == 1.0
