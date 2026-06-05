"""Tests for F1 (concentration stats) and F2 (moving-block bootstrap) — TDD.

Write BEFORE implementation so all tests must fail on first run.
"""

from __future__ import annotations

from application.precision_metrics import (
    date_level_significance,
    moving_block_bootstrap,
)

# ---------------------------------------------------------------------------
# F2 — moving_block_bootstrap
# ---------------------------------------------------------------------------


def test_mbb_strongly_positive_ci_above_zero() -> None:
    """All-positive series → CI entirely above zero, p_value_ge_0 < 0.05."""
    series = [0.02, 0.03, 0.025, 0.02, 0.028, 0.022]
    result = moving_block_bootstrap(series)
    assert result["ci_low"] is not None
    assert result["ci_high"] is not None
    assert result["ci_low"] > 0, f"ci_low={result['ci_low']} should be > 0"
    assert result["p_value_ge_0"] is not None
    assert (
        result["p_value_ge_0"] < 0.05
    ), f"p_value_ge_0={result['p_value_ge_0']} should be < 0.05"


def test_mbb_zero_mean_ci_not_entirely_positive() -> None:
    """Symmetric zero-mean series → CI is not entirely above 0, p_value_ge_0 is NOT small.

    With a perfectly alternating series the MBB correctly shows no positive mean:
    ci_low < 0 (bootstraps can go negative), ci_high >= 0 (non-negative upper bound),
    and p_value_ge_0 is large (≥ 0.2), meaning there is NO evidence of a positive mean.
    """
    series = [0.02, -0.02, 0.015, -0.015, 0.01, -0.01]
    result = moving_block_bootstrap(series)
    assert result["ci_low"] is not None
    assert result["ci_high"] is not None
    # CI is not entirely positive (evidence the mean is not robustly > 0)
    assert result["ci_low"] < 0, f"ci_low={result['ci_low']} should be < 0"
    assert result["ci_high"] >= 0, f"ci_high={result['ci_high']} should be >= 0"
    # p_value_ge_0 is large — no robust positive mean signal
    assert result["p_value_ge_0"] is not None
    assert (
        result["p_value_ge_0"] > 0.2
    ), f"p_value_ge_0={result['p_value_ge_0']} should be > 0.2"


def test_mbb_deterministic_same_seed() -> None:
    """Same seed must produce identical results; different seeds may differ."""
    series = [0.01, 0.02, -0.01, 0.03, 0.015, -0.005, 0.008, 0.012]
    r1 = moving_block_bootstrap(series, seed=42)
    r2 = moving_block_bootstrap(series, seed=42)
    assert r1["ci_low"] == r2["ci_low"]
    assert r1["ci_high"] == r2["ci_high"]
    assert r1["p_value_ge_0"] == r2["p_value_ge_0"]

    r3 = moving_block_bootstrap(series, seed=99999)
    # With different seed, at least one result should (very likely) differ
    # We allow this test to be soft — just confirm no exception with different seed
    assert r3["n"] == r1["n"]


def test_mbb_degenerate_single_value() -> None:
    """n<2 → ci_low/ci_high/p_value_ge_0 are None, n_resamples == 0, no exception."""
    result = moving_block_bootstrap([0.05])
    assert result["ci_low"] is None
    assert result["ci_high"] is None
    assert result["p_value_ge_0"] is None
    assert result["n_resamples"] == 0
    assert result["n"] == 1


def test_mbb_degenerate_empty() -> None:
    """Empty list → degenerate, mean == 0.0, no exception."""
    result = moving_block_bootstrap([])
    assert result["ci_low"] is None
    assert result["n_resamples"] == 0
    assert result["mean"] == 0.0
    assert result["n"] == 0


def test_mbb_returns_required_keys() -> None:
    """Result dict must contain all specified keys."""
    series = [0.01, 0.02, 0.03, 0.015, 0.025, 0.01]
    result = moving_block_bootstrap(series)
    required = {
        "n",
        "block_size",
        "n_resamples",
        "mean",
        "ci_low",
        "ci_high",
        "p_value_ge_0",
    }
    assert required.issubset(result.keys()), f"Missing keys: {required - result.keys()}"


def test_mbb_block_size_default_formula() -> None:
    """Default block_size = max(2, round(n^(1/3))), clamped to <= n."""
    # n=8 → n^(1/3)=2.0 → max(2, 2)=2
    result = moving_block_bootstrap([0.01] * 8)
    assert result["block_size"] == 2

    # n=27 → n^(1/3)=3.0 → max(2, 3)=3
    result27 = moving_block_bootstrap([0.01] * 27)
    assert result27["block_size"] == 3


def test_mbb_custom_block_size() -> None:
    """Custom block_size is respected."""
    series = [0.01, 0.02, 0.03, 0.015, 0.025, 0.01]
    result = moving_block_bootstrap(series, block_size=3)
    assert result["block_size"] == 3


def test_mbb_n_resamples_respected() -> None:
    """n_resamples parameter controls number of bootstrap samples."""
    series = [0.01, 0.02, 0.03, 0.015, 0.025, 0.01]
    result = moving_block_bootstrap(series, n_resamples=500)
    assert result["n_resamples"] == 500


# ---------------------------------------------------------------------------
# F1 — concentration stats in date_level_significance
# ---------------------------------------------------------------------------


def test_dls_concentration_one_dominant_date() -> None:
    """One massive positive date → top1_date_share ≈ 0.97."""
    model = [0.5, 0.01, 0.0, 0.0, 0.005]
    spy = [0.0, 0.0, 0.0, 0.0, 0.0]
    result = date_level_significance(model, spy)

    assert "top1_date_share" in result
    assert "top3_date_share" in result
    assert "per_date_excess" in result

    expected_top1 = 0.5 / (0.5 + 0.01 + 0.005)  # ≈ 0.9709
    assert result["top1_date_share"] is not None
    assert abs(result["top1_date_share"] - expected_top1) < 0.01


def test_dls_per_date_excess_length() -> None:
    """per_date_excess has same length as input and values are rounded."""
    model = [0.5, 0.01, 0.0, 0.0, 0.005]
    spy = [0.0, 0.0, 0.0, 0.0, 0.0]
    result = date_level_significance(model, spy)
    assert len(result["per_date_excess"]) == 5  # type: ignore[arg-type]


def test_dls_contains_bootstrap_dict() -> None:
    """date_level_significance output must include 'bootstrap' as a nested dict."""
    model = [0.02, 0.03, 0.025, 0.02, 0.03]
    spy = [0.0, 0.0, 0.0, 0.0, 0.0]
    result = date_level_significance(model, spy)

    assert "bootstrap" in result
    bootstrap = result["bootstrap"]
    assert isinstance(bootstrap, dict)
    assert "ci_low" in bootstrap
    assert "ci_high" in bootstrap
    assert "p_value_ge_0" in bootstrap


def test_dls_new_keys_present() -> None:
    """All four new keys are present in the non-degenerate path."""
    model = [0.02, 0.03, 0.025, 0.02, 0.03]
    spy = [0.0, 0.0, 0.0, 0.0, 0.0]
    result = date_level_significance(model, spy)
    for key in ("per_date_excess", "top1_date_share", "top3_date_share", "bootstrap"):
        assert key in result, f"Missing key: {key}"


def test_dls_degenerate_path_has_new_keys() -> None:
    """Even in the degenerate path (n<2), new keys must be present."""
    result = date_level_significance([], [])
    assert "per_date_excess" in result
    assert "top1_date_share" in result
    assert "top3_date_share" in result
    assert "bootstrap" in result
    assert result["top1_date_share"] is None
    assert result["top3_date_share"] is None


def test_dls_all_negative_excess_concentration_none() -> None:
    """No positive excess → pos_sum=0 → top1_date_share and top3_date_share are None."""
    model = [0.0, 0.0, 0.0]
    spy = [0.01, 0.01, 0.01]
    result = date_level_significance(model, spy)
    assert result["top1_date_share"] is None
    assert result["top3_date_share"] is None


def test_dls_top3_share_near_one_when_dominated() -> None:
    """When 3 dates account for almost all positive gains, top3_date_share close to 1."""
    # 3 big dates, many tiny ones
    model = [0.5, 0.4, 0.3] + [0.001] * 10
    spy = [0.0] * 13
    result = date_level_significance(model, spy)
    assert result["top3_date_share"] is not None
    # top3 / total_positive should be > 0.95
    total_pos = 0.5 + 0.4 + 0.3 + 0.001 * 10
    expected = (0.5 + 0.4 + 0.3) / total_pos
    assert abs(result["top3_date_share"] - expected) < 0.02
