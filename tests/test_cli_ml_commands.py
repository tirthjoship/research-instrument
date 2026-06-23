"""CLI tests for ML commands (run-tournament pre-flight guard)."""

from __future__ import annotations

from unittest.mock import patch

from click.testing import CliRunner

from adapters.ml.ensemble_predictor import EnsemblePredictor
from application.cli._cli_group import cli


def test_run_tournament_exits_nonzero_when_predictors_not_fitted() -> None:
    """Unfitted predictors must cause exit code 1, not silent 0-pick success."""
    runner = CliRunner()
    unfitted = {
        "2d": EnsemblePredictor(random_seed=42),
        "5d": EnsemblePredictor(random_seed=43),
        "10d": EnsemblePredictor(random_seed=44),
    }

    fake_deps: dict[str, object] = {
        "predictors": unfitted,
        "market_data": None,
        "technical_analysis": None,
        "feature_engineer": None,
        "store": None,
        "config": {"tickers": ["AAPL"]},
        "macro_symbols": [],
        "fundamental_engineer": None,
        "cross_asset_engineer": None,
        "event_causal_engineer": None,
    }

    with patch(
        "application.cli.ml_commands._build_dependencies", return_value=fake_deps
    ):
        result = runner.invoke(cli, ["run-tournament"])

    assert result.exit_code == 1
    assert "not trained" in (result.output + str(result.exception)).lower()
