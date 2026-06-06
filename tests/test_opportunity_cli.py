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


def test_drip_backfill_invalid_source_rejected() -> None:
    from click.testing import CliRunner

    from application.cli import cli

    runner = CliRunner()
    result = runner.invoke(
        cli, ["drip-backfill", "--source", "nonsense", "--limit", "1"]
    )
    assert result.exit_code != 0
    assert "nonsense" in result.output or "Invalid value" in result.output


def test_validate_divergence_ic_runs(monkeypatch: object) -> None:
    from click.testing import CliRunner

    import application.cli as climod
    from application.cli import cli

    class _UC:
        def __init__(self, *a: object, **k: object) -> None:
            pass

        def execute(self, dates: list, tickers: list, horizon_label: str) -> dict:
            return {
                "horizon": horizon_label,
                "mean_ic": 0.031,
                "ic_ir": 0.5,
                "pct_positive_dates": 0.6,
                "n_dates": 40,
                "bootstrap": {"ci_low": 0.01, "ci_high": 0.05, "p_value_ge_0": 0.01},
                "date_level": {},
            }

    import pytest  # noqa: F401  (monkeypatch type hint workaround)

    monkeypatch.setattr(climod, "DivergenceICBacktestUseCase", _UC, raising=False)  # type: ignore[attr-defined]

    runner = CliRunner()
    result = runner.invoke(cli, ["validate-divergence-ic", "--limit", "5", "--quick"])
    assert result.exit_code == 0, result.output
    assert "mean_ic" in result.output.lower() or "IC" in result.output
    assert "PROCEED" in result.output or "KILL" in result.output


def test_validate_divergence_ic_passes_naive_dates(monkeypatch: object) -> None:
    from click.testing import CliRunner

    import application.cli as climod
    from application.cli import cli

    captured: dict = {}

    class _UC:
        def __init__(self, *a: object, **k: object) -> None:
            pass

        def execute(self, dates: list, tickers: list, horizon_label: str) -> dict:
            captured["dates"] = dates
            return {
                "horizon": horizon_label,
                "mean_ic": 0.0,
                "ic_ir": 0.0,
                "pct_positive_dates": 0.0,
                "n_dates": 0,
                "bootstrap": {},
                "date_level": {},
            }

    monkeypatch.setattr(climod, "DivergenceICBacktestUseCase", _UC, raising=False)  # type: ignore[attr-defined]

    runner = CliRunner()
    result = runner.invoke(cli, ["validate-divergence-ic", "--limit", "2", "--quick"])
    assert result.exit_code == 0, result.output
    assert captured["dates"], "no dates generated"
    assert all(
        d.tzinfo is None for d in captured["dates"]
    ), "dates must be naive-UTC to match price/attention layers"


# ── R3: resolve-wiki-articles + _load_wiki_map merge ────────────────────────


def test_resolve_wiki_articles_writes_yaml(
    monkeypatch: object, tmp_path: object
) -> None:
    import yaml

    import application.cli as climod
    from application.cli import cli

    class _FakeResolver:
        def __init__(self, *a: object, **k: object) -> None:
            pass

        def resolve_validated(
            self, name: str, start: object, end: object, min_views: float = 50.0
        ) -> str | None:
            return "Apple Inc." if name == "Apple Inc." else None

    monkeypatch.setattr(climod, "WikipediaArticleResolver", _FakeResolver, raising=False)  # type: ignore[attr-defined]
    # Prevent the test from reading the real wiki_articles_us.yaml (which may have AAPL already)
    monkeypatch.setattr(climod, "_load_wiki_map", lambda market: {}, raising=False)  # type: ignore[attr-defined]

    names = {"AAPL": "Apple Inc.", "AIZ": "Assurant"}
    monkeypatch.setattr(climod, "_get_company_name", lambda deps, t: names.get(t), raising=False)  # type: ignore[attr-defined]
    monkeypatch.setattr(climod, "_get_ticker_universe", lambda config: ["AAPL", "AIZ"], raising=False)  # type: ignore[attr-defined]

    from pathlib import Path

    out = Path(str(tmp_path)) / "wiki_articles_us.yaml"  # type: ignore[arg-type]
    runner = CliRunner()
    result = runner.invoke(
        cli, ["resolve-wiki-articles", "--out", str(out), "--throttle-s", "0"]
    )
    assert result.exit_code == 0, result.output
    data = yaml.safe_load(out.read_text())
    assert data["AAPL"] == "Apple Inc."
    assert "AIZ" not in data
    # FIX 1: dropped ticker symbols must appear in the CLI output
    assert "AIZ" in result.output


def test_resolve_wiki_articles_skips_existing_alias(
    monkeypatch: object, tmp_path: object
) -> None:
    import application.cli as climod
    from application.cli import cli

    seen: list[str] = []

    class _FakeResolver:
        def __init__(self, *a: object, **k: object) -> None:
            pass

        def resolve_validated(
            self, name: str, start: object, end: object, min_views: float = 50.0
        ) -> str | None:
            seen.append(name)
            return "X"

    monkeypatch.setattr(climod, "WikipediaArticleResolver", _FakeResolver, raising=False)  # type: ignore[attr-defined]
    monkeypatch.setattr(climod, "_get_company_name", lambda deps, t: "Name " + t, raising=False)  # type: ignore[attr-defined]
    # Pin the curated skip set in-test (isolate from live on-disk wiki_articles_us.yaml):
    # RKLB as a curated alias must be skipped, resolver never called for it.
    monkeypatch.setattr(climod, "_load_wiki_map", lambda market: {"RKLB": "Rocket_Lab"}, raising=False)  # type: ignore[attr-defined]
    monkeypatch.setattr(climod, "_get_ticker_universe", lambda config: ["RKLB"], raising=False)  # type: ignore[attr-defined]

    from pathlib import Path

    out = Path(str(tmp_path)) / "wiki_articles_us.yaml"  # type: ignore[arg-type]
    runner = CliRunner()
    result = runner.invoke(
        cli, ["resolve-wiki-articles", "--out", str(out), "--throttle-s", "0"]
    )
    assert result.exit_code == 0, result.output
    assert "Name RKLB" not in seen


def test_load_wiki_map_merged_aliases_win(
    monkeypatch: object, tmp_path: object
) -> None:
    """_load_wiki_map_merged: curated aliases win over resolved YAML; resolved entries added."""
    from pathlib import Path

    import application.cli as climod

    resolved = Path(str(tmp_path)) / "wiki_articles_us.yaml"  # type: ignore[arg-type]
    resolved.write_text("RKLB: WRONG_Override\nAAPL: Apple Inc.\n")

    m = climod._load_wiki_map_merged(market="us", resolved_path=str(resolved))
    # RKLB has a curated alias in themes.yaml ("Rocket_Lab") — must not be overridden
    assert m.get("RKLB") != "WRONG_Override"
    # AAPL is not in themes aliases → resolved entry present
    assert m.get("AAPL") == "Apple Inc."


def test_resolve_wiki_articles_skips_throttled(
    monkeypatch: object, tmp_path: object
) -> None:
    import yaml

    import application.cli as climod
    from application.cli import cli
    from domain.exceptions import SourceThrottledError

    class _FakeResolver:
        def __init__(self, *a: object, **k: object) -> None:
            pass

        def resolve_validated(
            self, name: str, start: object, end: object, min_views: float = 50.0
        ) -> str | None:
            if name == "Apple Inc.":
                raise SourceThrottledError("throttled")
            return "Abbott Laboratories"

    monkeypatch.setattr(climod, "WikipediaArticleResolver", _FakeResolver, raising=False)  # type: ignore[attr-defined]
    # Prevent reading real wiki_articles_us.yaml which may contain AAPL/ABT
    monkeypatch.setattr(climod, "_load_wiki_map", lambda market: {}, raising=False)  # type: ignore[attr-defined]

    names = {"AAPL": "Apple Inc.", "ABT": "Abbott Laboratories"}
    monkeypatch.setattr(climod, "_get_company_name", lambda deps, t: names.get(t), raising=False)  # type: ignore[attr-defined]
    monkeypatch.setattr(climod, "_get_ticker_universe", lambda config: ["AAPL", "ABT"], raising=False)  # type: ignore[attr-defined]

    from pathlib import Path

    out = Path(str(tmp_path)) / "w.yaml"  # type: ignore[arg-type]
    runner = CliRunner()
    result = runner.invoke(
        cli, ["resolve-wiki-articles", "--out", str(out), "--throttle-s", "0"]
    )
    assert result.exit_code == 0, result.output
    data = yaml.safe_load(out.read_text()) or {}
    assert "AAPL" not in data  # throttled -> skipped, NOT written
    assert data.get("ABT") == "Abbott Laboratories"
    assert "AAPL" in result.output  # throttled ticker named in summary
