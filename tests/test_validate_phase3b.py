"""Tests for Phase 3B end-to-end validation orchestrator."""

from __future__ import annotations

from datetime import datetime

import pytest

from application.validate_phase3b import Phase3BValidator, ValidationReport
from domain.models import BuzzSignal


@pytest.fixture
def sample_buzz_signals() -> list[BuzzSignal]:
    signals = []
    for i in range(20):
        signals.append(
            BuzzSignal(
                ticker="AAPL",
                source="reuters",
                mention_count=1,
                sentiment_raw=0.0,
                scorer="rss_raw",
                fetched_at=datetime(2026, 5, 30, 10, i),
                article_hash=f"raw_{i}",
            )
        )
    for i in range(10):
        signals.append(
            BuzzSignal(
                ticker="AAPL",
                source="reuters",
                mention_count=1,
                sentiment_raw=0.4 + (i * 0.05),
                scorer="keyword",
                fetched_at=datetime(2026, 5, 30, 10, i),
                article_hash=f"kw_{i}",
            )
        )
    return signals


@pytest.fixture
def sample_prior_signals() -> list[BuzzSignal]:
    return [
        BuzzSignal(
            ticker="AAPL",
            source="reuters",
            mention_count=1,
            sentiment_raw=0.3,
            scorer="keyword",
            fetched_at=datetime(2026, 5, 23, 10, i),
            article_hash=f"prior_{i}",
        )
        for i in range(5)
    ]


def test_validator_produces_report(
    sample_buzz_signals: list[BuzzSignal],
    sample_prior_signals: list[BuzzSignal],
) -> None:
    validator = Phase3BValidator()
    report = validator.validate(
        buzz_current={"AAPL": sample_buzz_signals},
        buzz_prior={"AAPL": sample_prior_signals},
        stage1_predictions={"AAPL": [0.01, -0.02, 0.015, -0.01, 0.005]},
        actual_returns={"AAPL": [0.02, -0.01, 0.01, -0.015, 0.008]},
    )
    assert isinstance(report, ValidationReport)
    assert len(report.ablation_results) == 3
    assert report.tickers_evaluated > 0


def test_validator_handles_empty_buzz() -> None:
    validator = Phase3BValidator()
    report = validator.validate(
        buzz_current={},
        buzz_prior={},
        stage1_predictions={"AAPL": [0.01, -0.02]},
        actual_returns={"AAPL": [0.02, -0.01]},
    )
    assert report.tickers_evaluated == 0
    assert report.ablation_results[0]["variant"] == "technical_only"


def test_validation_report_has_p_values(
    sample_buzz_signals: list[BuzzSignal],
    sample_prior_signals: list[BuzzSignal],
) -> None:
    validator = Phase3BValidator()
    report = validator.validate(
        buzz_current={"AAPL": sample_buzz_signals},
        buzz_prior={"AAPL": sample_prior_signals},
        stage1_predictions={"AAPL": [0.01, -0.02, 0.015, -0.01, 0.005]},
        actual_returns={"AAPL": [0.02, -0.01, 0.01, -0.015, 0.008]},
    )
    for result in report.ablation_results:
        assert "p_value" in result


def test_validation_report_serializes_to_dict(
    sample_buzz_signals: list[BuzzSignal],
    sample_prior_signals: list[BuzzSignal],
) -> None:
    validator = Phase3BValidator()
    report = validator.validate(
        buzz_current={"AAPL": sample_buzz_signals},
        buzz_prior={"AAPL": sample_prior_signals},
        stage1_predictions={"AAPL": [0.01, -0.02, 0.015, -0.01, 0.005]},
        actual_returns={"AAPL": [0.02, -0.01, 0.01, -0.015, 0.008]},
    )
    d = report.to_dict()
    assert "ablation_results" in d
    assert "tickers_evaluated" in d
    assert "timestamp" in d


def test_validate_3b_cli_command_exists() -> None:
    """The validate-3b CLI command should be registered."""
    from click.testing import CliRunner

    from application.cli import cli

    runner = CliRunner()
    result = runner.invoke(cli, ["validate-3b", "--help"])
    assert result.exit_code == 0
    assert "validate" in result.output.lower() or "3b" in result.output.lower()
