"""Tests for resolve-corroboration and corroboration-calibration-status CLI commands."""

from __future__ import annotations

from datetime import date, timedelta
from pathlib import Path
from typing import Literal
from unittest.mock import patch

from click.testing import CliRunner

from application.cli._cli_group import cli
from domain.corroboration_gate import GateResult, GateSample

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _sample(ticker: str = "AAPL", excess: float = 0.02) -> GateSample:
    snap = date(2026, 1, 1)
    return GateSample(
        ticker=ticker,
        snapshot_date=snap,
        resolved_at=snap + timedelta(days=21),
        excess_21d=excess,
        excess_63d=None,
        beat_spy_21d=excess > 0,
    )


def _gate_result(
    verdict: Literal["PENDING", "PASS", "FAIL"] = "PASS",
    n: int = 30,
    mean_21d: float = 0.0031,
    ci_lower: float = -0.0012,
    ci_upper: float = 0.0074,
    hit_rate: float = 0.58,
    mean_63d: float | None = None,
) -> GateResult:
    return GateResult(
        n_resolved=n,
        mean_excess_21d=mean_21d,
        ci_lower=ci_lower,
        ci_upper=ci_upper,
        hit_rate_21d=hit_rate,
        mean_excess_63d=mean_63d,
        verdict=verdict,
        evaluated_at=date(2026, 6, 23),
    )


# ---------------------------------------------------------------------------
# resolve-corroboration tests
# ---------------------------------------------------------------------------


def test_resolve_pending_output(tmp_path: Path) -> None:
    """< 30 samples => PENDING + count in output."""
    runner = CliRunner()
    two_samples = [_sample(), _sample("MSFT")]

    with (
        patch(
            "application.cli.corroboration_commands.CorroborationResolverUseCase"
        ) as mock_uc_cls,
        patch("application.cli.corroboration_commands.append_samples", return_value=2),
        patch(
            "application.cli.corroboration_commands.load_samples",
            return_value=two_samples,
        ),
        patch(
            "application.cli.corroboration_commands.load_latest_result",
            return_value=None,
        ),
        patch("application.cli.corroboration_commands.sqlite3"),
        patch("application.cli.corroboration_commands.CorroborationStore"),
        patch("application.cli.corroboration_commands.YFinancePriceResolver"),
    ):
        mock_uc_cls.return_value.resolve.return_value = two_samples
        result = runner.invoke(cli, ["resolve-corroboration", "--as-of", "2026-06-23"])

    assert result.exit_code == 0, result.output
    assert "2 new samples" in result.output
    assert "total: 2" in result.output
    assert "PENDING" in result.output


def test_resolve_gate_evaluates_at_30_samples() -> None:
    """Exactly 30 samples => gate evaluated, verdict shown."""
    runner = CliRunner()
    thirty_samples = [_sample(f"T{i}", 0.01) for i in range(30)]
    pass_result = _gate_result(verdict="PASS", n=30)

    with (
        patch(
            "application.cli.corroboration_commands.CorroborationResolverUseCase"
        ) as mock_uc_cls,
        patch("application.cli.corroboration_commands.append_samples", return_value=30),
        patch(
            "application.cli.corroboration_commands.load_samples",
            return_value=thirty_samples,
        ),
        patch(
            "application.cli.corroboration_commands.load_latest_result",
            return_value=None,
        ),
        patch(
            "application.cli.corroboration_commands.append_result"
        ) as mock_append_result,
        patch(
            "application.cli.corroboration_commands.evaluate_gate",
            return_value=pass_result,
        ),
        patch("application.cli.corroboration_commands.sqlite3"),
        patch("application.cli.corroboration_commands.CorroborationStore"),
        patch("application.cli.corroboration_commands.YFinancePriceResolver"),
    ):
        mock_uc_cls.return_value.resolve.return_value = thirty_samples
        result = runner.invoke(cli, ["resolve-corroboration", "--as-of", "2026-06-23"])

    assert result.exit_code == 0, result.output
    assert "PASS" in result.output
    mock_append_result.assert_called_once_with(pass_result)


def test_resolve_fail_prints_warning() -> None:
    """FAIL verdict => warning visible in combined output."""
    runner = CliRunner()
    thirty_samples = [_sample(f"T{i}", -0.005) for i in range(30)]
    fail_result = _gate_result(verdict="FAIL", n=30, mean_21d=-0.005, hit_rate=0.4)

    with (
        patch(
            "application.cli.corroboration_commands.CorroborationResolverUseCase"
        ) as mock_uc_cls,
        patch("application.cli.corroboration_commands.append_samples", return_value=30),
        patch(
            "application.cli.corroboration_commands.load_samples",
            return_value=thirty_samples,
        ),
        patch(
            "application.cli.corroboration_commands.load_latest_result",
            return_value=None,
        ),
        patch("application.cli.corroboration_commands.append_result"),
        patch(
            "application.cli.corroboration_commands.evaluate_gate",
            return_value=fail_result,
        ),
        patch("application.cli.corroboration_commands.sqlite3"),
        patch("application.cli.corroboration_commands.CorroborationStore"),
        patch("application.cli.corroboration_commands.YFinancePriceResolver"),
    ):
        mock_uc_cls.return_value.resolve.return_value = thirty_samples
        result = runner.invoke(cli, ["resolve-corroboration", "--as-of", "2026-06-23"])

    assert "FAIL" in result.output
    assert "HYPOTHESIS #9 FAILED" in result.output


# ---------------------------------------------------------------------------
# corroboration-calibration-status tests
# ---------------------------------------------------------------------------


def test_calibration_status_no_data() -> None:
    """0 samples => PENDING + n/a stats."""
    runner = CliRunner()

    with (
        patch("application.cli.corroboration_commands.load_samples", return_value=[]),
        patch(
            "application.cli.corroboration_commands.load_latest_result",
            return_value=None,
        ),
    ):
        result = runner.invoke(cli, ["corroboration-calibration-status"])

    assert result.exit_code == 0, result.output
    assert "PENDING" in result.output
    assert "0" in result.output
    assert "n/a" in result.output


def test_calibration_status_pending_with_samples() -> None:
    """12 samples, no result => PENDING + 12/30."""
    runner = CliRunner()
    pending_samples = [_sample(f"T{i}") for i in range(12)]

    with (
        patch(
            "application.cli.corroboration_commands.load_samples",
            return_value=pending_samples,
        ),
        patch(
            "application.cli.corroboration_commands.load_latest_result",
            return_value=None,
        ),
    ):
        result = runner.invoke(cli, ["corroboration-calibration-status"])

    assert result.exit_code == 0, result.output
    assert "PENDING" in result.output
    assert "12" in result.output
    assert "30" in result.output
    assert "RESEARCH_ONLY" in result.output
    assert "ADR-064" in result.output


def test_calibration_status_with_result() -> None:
    """Latest result present => shows its fields."""
    runner = CliRunner()
    thirty_samples = [_sample(f"T{i}") for i in range(30)]
    gate_res = _gate_result(
        verdict="PASS",
        n=30,
        mean_21d=0.0031,
        ci_lower=-0.0012,
        ci_upper=0.0074,
        hit_rate=0.58,
    )

    with (
        patch(
            "application.cli.corroboration_commands.load_samples",
            return_value=thirty_samples,
        ),
        patch(
            "application.cli.corroboration_commands.load_latest_result",
            return_value=gate_res,
        ),
    ):
        result = runner.invoke(cli, ["corroboration-calibration-status"])

    assert result.exit_code == 0, result.output
    assert "PASS" in result.output
    assert "+0.31%" in result.output
    assert "58%" in result.output
    assert "[-0.12%," in result.output


def test_calibration_status_shows_adr_lock_date() -> None:
    """Output contains gate lock date and ADR reference."""
    runner = CliRunner()

    with (
        patch("application.cli.corroboration_commands.load_samples", return_value=[]),
        patch(
            "application.cli.corroboration_commands.load_latest_result",
            return_value=None,
        ),
    ):
        result = runner.invoke(cli, ["corroboration-calibration-status"])

    assert "2026-06-23 (ADR-064)" in result.output


def test_calibration_status_shows_research_only() -> None:
    """Output always contains RESEARCH_ONLY."""
    runner = CliRunner()

    with (
        patch("application.cli.corroboration_commands.load_samples", return_value=[]),
        patch(
            "application.cli.corroboration_commands.load_latest_result",
            return_value=None,
        ),
    ):
        result = runner.invoke(cli, ["corroboration-calibration-status"])

    assert "RESEARCH_ONLY" in result.output


# ---------------------------------------------------------------------------
# Alias tests from brief (kept for coverage parity)
# ---------------------------------------------------------------------------


def test_resolve_corroboration_pending_output(tmp_path: Path) -> None:
    """Alias: same as test_resolve_pending_output — brief name."""
    runner = CliRunner()
    two_samples = [_sample(), _sample("MSFT")]

    with (
        patch(
            "application.cli.corroboration_commands.CorroborationResolverUseCase"
        ) as mock_uc_cls,
        patch("application.cli.corroboration_commands.append_samples", return_value=2),
        patch(
            "application.cli.corroboration_commands.load_samples",
            return_value=two_samples,
        ),
        patch(
            "application.cli.corroboration_commands.load_latest_result",
            return_value=None,
        ),
        patch("application.cli.corroboration_commands.sqlite3"),
        patch("application.cli.corroboration_commands.CorroborationStore"),
        patch("application.cli.corroboration_commands.YFinancePriceResolver"),
    ):
        mock_uc_cls.return_value.resolve.return_value = two_samples
        result = runner.invoke(cli, ["resolve-corroboration", "--as-of", "2026-06-23"])

    assert result.exit_code == 0, result.output
    assert "2 new samples" in result.output
    assert "PENDING" in result.output


def test_resolve_corroboration_fail_output(tmp_path: Path) -> None:
    """Alias: same as test_resolve_fail_prints_warning — brief name."""
    runner = CliRunner()
    thirty_samples = [_sample(f"T{i}", -0.005) for i in range(30)]
    fail_result = _gate_result(verdict="FAIL", n=30, mean_21d=-0.005, hit_rate=0.4)

    with (
        patch(
            "application.cli.corroboration_commands.CorroborationResolverUseCase"
        ) as mock_uc_cls,
        patch("application.cli.corroboration_commands.append_samples", return_value=30),
        patch(
            "application.cli.corroboration_commands.load_samples",
            return_value=thirty_samples,
        ),
        patch(
            "application.cli.corroboration_commands.load_latest_result",
            return_value=None,
        ),
        patch("application.cli.corroboration_commands.append_result"),
        patch(
            "application.cli.corroboration_commands.evaluate_gate",
            return_value=fail_result,
        ),
        patch("application.cli.corroboration_commands.sqlite3"),
        patch("application.cli.corroboration_commands.CorroborationStore"),
        patch("application.cli.corroboration_commands.YFinancePriceResolver"),
    ):
        mock_uc_cls.return_value.resolve.return_value = thirty_samples
        result = runner.invoke(cli, ["resolve-corroboration", "--as-of", "2026-06-23"])

    assert "FAIL" in result.output
    assert "HYPOTHESIS #9 FAILED" in result.output


def test_calibration_status_pending_output() -> None:
    """Alias: same as test_calibration_status_pending_with_samples — brief name."""
    runner = CliRunner()
    pending_samples = [_sample(f"T{i}") for i in range(12)]

    with (
        patch(
            "application.cli.corroboration_commands.load_samples",
            return_value=pending_samples,
        ),
        patch(
            "application.cli.corroboration_commands.load_latest_result",
            return_value=None,
        ),
    ):
        result = runner.invoke(cli, ["corroboration-calibration-status"])

    assert result.exit_code == 0, result.output
    assert "PENDING" in result.output
    assert "12" in result.output
    assert "30" in result.output
    assert "RESEARCH_ONLY" in result.output
    assert "ADR-064" in result.output


def test_calibration_status_no_samples_output() -> None:
    """Alias: same as test_calibration_status_no_data — brief name."""
    runner = CliRunner()

    with (
        patch("application.cli.corroboration_commands.load_samples", return_value=[]),
        patch(
            "application.cli.corroboration_commands.load_latest_result",
            return_value=None,
        ),
    ):
        result = runner.invoke(cli, ["corroboration-calibration-status"])

    assert result.exit_code == 0
    assert "0" in result.output
    assert "PENDING" in result.output
