"""Tests for enhanced backtest report with p-values and Sharpe ratio."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from application.backtest_runner import (
    compute_binomial_pvalue,
    compute_sharpe_vs_spy,
    run_backtest_report,
)


def test_binomial_pvalue_random_accuracy() -> None:
    p = compute_binomial_pvalue(accuracy=0.50, n_predictions=760)
    assert p > 0.05


def test_binomial_pvalue_strong_accuracy() -> None:
    p = compute_binomial_pvalue(accuracy=0.60, n_predictions=760)
    assert p < 0.01


def test_binomial_pvalue_edge_zero_predictions() -> None:
    p = compute_binomial_pvalue(accuracy=0.50, n_predictions=0)
    assert p == 1.0


def test_sharpe_vs_spy_flat_returns() -> None:
    model_returns = [0.0] * 12
    spy_returns = [0.01] * 12
    result = compute_sharpe_vs_spy(model_returns, spy_returns)
    assert "model_sharpe" in result
    assert "spy_sharpe" in result
    assert "excess_sharpe" in result
    assert result["excess_sharpe"] < 0


def test_sharpe_vs_spy_empty_returns() -> None:
    result = compute_sharpe_vs_spy([], [])
    assert result["model_sharpe"] == 0.0
    assert result["spy_sharpe"] == 0.0


def test_backtest_report_includes_pvalue_and_sharpe() -> None:
    from domain.models import EvaluationRun

    mock_store = MagicMock()
    mock_store.get_evaluation_runs.return_value = [
        EvaluationRun(
            run_date=f"2025-{m:02d}",
            eval_type="walk_forward",
            horizon="5d",
            metric_name="directional_accuracy",
            metric_value=0.52,
        )
        for m in range(1, 20)
    ]

    with patch("adapters.data.sqlite_store.SQLiteStore", return_value=mock_store):
        report = run_backtest_report()

    horizons = report.get("horizons", {})
    assert "5d" in horizons
    h5 = horizons["5d"]
    assert "p_value_vs_random" in h5
    assert "n_total_predictions" in h5
