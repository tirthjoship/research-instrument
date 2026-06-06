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


def test_daily_cycle_invokes_scan_then_resolve(monkeypatch: object) -> None:
    import application.cli as climod

    class _ScanUC:
        def __init__(self, *a: object, **k: object) -> None:
            pass

        def execute(
            self, now: object, *, allow_abstention: bool = True
        ) -> list[object]:
            return []

    class _ResolveUC:
        def __init__(self, *a: object, **k: object) -> None:
            pass

        def resolve_due_calls(self, now: object) -> list[object]:
            return []

    monkeypatch.setattr(climod, "OpportunityScanUseCase", _ScanUC)  # type: ignore[attr-defined]
    monkeypatch.setattr(
        "application.forward_tracking_use_case.ForwardTrackingUseCase",
        _ResolveUC,
    )
    # Also patch the climod reference since forward_tracking_use_case is imported inside
    # the resolve_calls command body; we patch the class in its own module so that
    # the local `from application.forward_tracking_use_case import ForwardTrackingUseCase`
    # inside resolve_calls picks up the stub.
    import application.forward_tracking_use_case as ftmod

    monkeypatch.setattr(ftmod, "ForwardTrackingUseCase", _ResolveUC)  # type: ignore[attr-defined]

    runner = CliRunner()
    result = runner.invoke(cli, ["daily-cycle", "--skip-backfill"])
    assert result.exit_code == 0, result.output
    assert "daily cycle" in result.output.lower()


def test_drip_backfill_command_runs(monkeypatch: object) -> None:
    import application.cli as climod
    from domain.models import SourceHealth

    class _UC:
        def __init__(self, *a: object, **k: object) -> None:
            pass

        def execute(
            self, tickers: list[str], now: object, days: int = 90
        ) -> dict[str, object]:
            return {"google_trends": SourceHealth("google_trends", attempts=1, ok=1)}

    monkeypatch.setattr(climod, "DripBackfillUseCase", _UC, raising=False)  # type: ignore[attr-defined]

    runner = CliRunner()
    result = runner.invoke(
        cli,
        [
            "drip-backfill",
            "--market",
            "us",
            "--days",
            "30",
            "--limit",
            "2",
            "--spine-only",
        ],
    )
    assert result.exit_code == 0, result.output
    assert "google_trends" in result.output


def test_drip_backfill_source_filter(monkeypatch: object) -> None:
    import application.cli as climod
    from domain.models import SourceHealth

    captured: dict[str, object] = {}

    class _UC:
        def __init__(
            self,
            sources: dict[str, object],
            store: object,
            sleep: object,
            throttle_s: float = 45.0,
        ) -> None:
            captured["sources"] = list(sources.keys())

        def execute(
            self, tickers: list[str], now: object, days: int = 90
        ) -> dict[str, object]:
            return {"wikipedia": SourceHealth("wikipedia", attempts=1, ok=1)}

    monkeypatch.setattr(climod, "DripBackfillUseCase", _UC, raising=False)  # type: ignore[attr-defined]

    runner = CliRunner()
    result = runner.invoke(
        cli, ["drip-backfill", "--source", "wikipedia", "--limit", "3"]
    )
    assert result.exit_code == 0, result.output
    assert captured["sources"] == ["wikipedia"]  # only wikipedia wired


def test_audit_command_runs(monkeypatch: object) -> None:
    import application.cli as climod

    class _Store:
        def get_scan_candidates(
            self, scan_date: object = None
        ) -> list[dict[str, object]]:
            return [
                {
                    "ticker": "A",
                    "sub_scores": {"smart_money": 8.0, "event_signal": 5.0},
                },
                {
                    "ticker": "B",
                    "sub_scores": {"smart_money": 3.0, "event_signal": 5.0},
                },
            ]

    def _deps(market: str) -> dict[str, object]:
        return {"store": _Store(), "config": {}}

    monkeypatch.setattr(climod, "_build_dependencies", _deps, raising=False)  # type: ignore[attr-defined]

    runner = CliRunner()
    result = runner.invoke(cli, ["audit-dimensions"])
    assert result.exit_code == 0, result.output
    assert "event_signal" in result.output
    assert "neutral" in result.output.lower()


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
