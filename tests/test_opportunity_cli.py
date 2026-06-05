"""Smoke tests for scan-opportunities, resolve-calls, opportunity-report CLI commands."""

from click.testing import CliRunner

from application.cli import cli


def test_commands_registered() -> None:
    names = {c.name for c in cli.commands.values()}
    assert {"scan-opportunities", "resolve-calls", "opportunity-report"} <= names


def test_scan_help_renders() -> None:
    res = CliRunner().invoke(cli, ["scan-opportunities", "--help"])
    assert res.exit_code == 0
    assert "surface" in res.output.lower()


def test_scan_show_all_prints_distribution(monkeypatch: object) -> None:
    import application.cli as climod

    class _UC:
        def __init__(self, *a: object, **k: object) -> None:
            pass

        def execute(
            self, now: object, *, allow_abstention: bool = True
        ) -> list[object]:
            return []

    # OpportunityScanUseCase is now a module-level import in cli.py, so
    # patching climod.OpportunityScanUseCase intercepts the constructor call.
    monkeypatch.setattr(climod, "OpportunityScanUseCase", _UC)  # type: ignore[attr-defined]

    runner = CliRunner()
    result = runner.invoke(cli, ["scan-opportunities", "--show-all"])
    assert result.exit_code == 0, result.output


def test_backfill_history_command_runs(monkeypatch: object, tmp_path: object) -> None:
    import application.cli as climod

    class _UC:
        def __init__(self, *a: object, **k: object) -> None:
            pass

        def execute(
            self, tickers: list[str], now: object, days: int = 90
        ) -> dict[str, int]:
            return {"tickers": len(tickers), "errors": 0}

    monkeypatch.setattr(climod, "BackfillHistoryUseCase", _UC, raising=False)  # type: ignore[attr-defined]

    runner = CliRunner()
    result = runner.invoke(
        cli, ["backfill-history", "--market", "us", "--days", "30", "--limit", "2"]
    )
    assert result.exit_code == 0, result.output
    assert "Backfill complete" in result.output
