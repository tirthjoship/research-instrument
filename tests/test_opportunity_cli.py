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
    class _UC:
        def __init__(self, *a: object, **k: object) -> None:
            pass

        def execute(
            self, now: object, *, allow_abstention: bool = True
        ) -> list[object]:
            return []

    # OpportunityScanUseCase is a lazy import inside scan_commands.scan_opportunities();
    # patch it at the source module so the lazy `from ... import` picks up the stub.
    import application.opportunity_scan_use_case as _opp_mod

    monkeypatch.setattr(_opp_mod, "OpportunityScanUseCase", _UC)  # type: ignore[attr-defined]

    runner = CliRunner()
    result = runner.invoke(cli, ["scan-opportunities", "--show-all"])
    assert result.exit_code == 0, result.output


def test_scan_opportunities_wires_market_benchmark_ticker(monkeypatch: object) -> None:
    """scan-opportunities --market ca must pass the CA benchmark (XIC.TO) through
    to OpportunityScanUseCase, not silently default to US SPY (final-review
    Finding 1, site A)."""
    captured: dict[str, object] = {}

    class _UC:
        def __init__(self, *a: object, **k: object) -> None:
            captured.update(k)

        def execute(
            self, now: object, *, allow_abstention: bool = True
        ) -> list[object]:
            return []

    import application.opportunity_scan_use_case as _opp_mod

    monkeypatch.setattr(_opp_mod, "OpportunityScanUseCase", _UC)  # type: ignore[attr-defined]

    runner = CliRunner()
    result = runner.invoke(cli, ["scan-opportunities", "--market", "ca"])
    assert result.exit_code == 0, result.output
    assert captured["benchmark_ticker"] == "XIC.TO"


def test_daily_cycle_invokes_scan_then_resolve(monkeypatch: object) -> None:
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

    import application.opportunity_scan_use_case as _opp_mod

    monkeypatch.setattr(_opp_mod, "OpportunityScanUseCase", _ScanUC)  # type: ignore[attr-defined]
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
    import application.cli.data_commands as _data_cmd
    from domain.models import SourceHealth

    class _UC:
        def __init__(self, *a: object, **k: object) -> None:
            pass

        def execute(
            self, tickers: list[str], now: object, days: int = 90
        ) -> dict[str, object]:
            return {"google_trends": SourceHealth("google_trends", attempts=1, ok=1)}

    monkeypatch.setattr(_data_cmd, "DripBackfillUseCase", _UC)  # type: ignore[attr-defined]

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
    import application.cli.data_commands as _data_cmd
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

    monkeypatch.setattr(_data_cmd, "DripBackfillUseCase", _UC)  # type: ignore[attr-defined]

    runner = CliRunner()
    result = runner.invoke(
        cli, ["drip-backfill", "--source", "wikipedia", "--limit", "3"]
    )
    assert result.exit_code == 0, result.output
    assert captured["sources"] == ["wikipedia"]  # only wikipedia wired


def test_audit_command_runs(monkeypatch: object) -> None:
    import application.cli.validation_commands as _val_cmd

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

    monkeypatch.setattr(_val_cmd, "_build_dependencies", _deps)  # type: ignore[attr-defined]

    runner = CliRunner()
    result = runner.invoke(cli, ["audit-dimensions"])
    assert result.exit_code == 0, result.output
    assert "event_signal" in result.output
    assert "neutral" in result.output.lower()


def test_backfill_history_command_runs(monkeypatch: object, tmp_path: object) -> None:
    import application.cli.data_commands as _data_cmd

    class _UC:
        def __init__(self, *a: object, **k: object) -> None:
            pass

        def execute(
            self, tickers: list[str], now: object, days: int = 90
        ) -> dict[str, int]:
            return {"tickers": len(tickers), "errors": 0}

    monkeypatch.setattr(_data_cmd, "BackfillHistoryUseCase", _UC)  # type: ignore[attr-defined]

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

    import application.cli.validation_commands as _val_cmd
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

    monkeypatch.setattr(_val_cmd, "DivergenceICBacktestUseCase", _UC)  # type: ignore[attr-defined]

    runner = CliRunner()
    result = runner.invoke(cli, ["validate-divergence-ic", "--limit", "5", "--quick"])
    assert result.exit_code == 0, result.output
    assert "mean_ic" in result.output.lower() or "IC" in result.output
    assert "PROCEED" in result.output or "KILL" in result.output


def test_validate_divergence_ic_passes_naive_dates(monkeypatch: object) -> None:
    from click.testing import CliRunner

    import application.cli.validation_commands as _val_cmd
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

    monkeypatch.setattr(_val_cmd, "DivergenceICBacktestUseCase", _UC)  # type: ignore[attr-defined]

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

    import application.cli.data_commands as _data_cmd
    from application.cli import cli

    class _FakeResolver:
        def __init__(self, *a: object, **k: object) -> None:
            pass

        def resolve_validated(
            self, name: str, start: object, end: object, min_views: float = 50.0
        ) -> str | None:
            return "Apple Inc." if name == "Apple Inc." else None

    monkeypatch.setattr(_data_cmd, "WikipediaArticleResolver", _FakeResolver)  # type: ignore[attr-defined]
    # Prevent the test from reading the real wiki_articles_us.yaml (which may have AAPL already)
    monkeypatch.setattr(_data_cmd, "_load_wiki_map", lambda market: {})  # type: ignore[attr-defined]

    names = {"AAPL": "Apple Inc.", "AIZ": "Assurant"}
    monkeypatch.setattr(_data_cmd, "_get_company_name", lambda deps, t: names.get(t))  # type: ignore[attr-defined]
    monkeypatch.setattr(_data_cmd, "_get_ticker_universe", lambda config: ["AAPL", "AIZ"])  # type: ignore[attr-defined]

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
    import application.cli.data_commands as _data_cmd
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

    monkeypatch.setattr(_data_cmd, "WikipediaArticleResolver", _FakeResolver)  # type: ignore[attr-defined]
    monkeypatch.setattr(_data_cmd, "_get_company_name", lambda deps, t: "Name " + t)  # type: ignore[attr-defined]
    # Pin the curated skip set in-test (isolate from live on-disk wiki_articles_us.yaml):
    # RKLB as a curated alias must be skipped, resolver never called for it.
    monkeypatch.setattr(_data_cmd, "_load_wiki_map", lambda market: {"RKLB": "Rocket_Lab"})  # type: ignore[attr-defined]
    monkeypatch.setattr(_data_cmd, "_get_ticker_universe", lambda config: ["RKLB"])  # type: ignore[attr-defined]

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

    import application.cli.data_commands as _data_cmd
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

    monkeypatch.setattr(_data_cmd, "WikipediaArticleResolver", _FakeResolver)  # type: ignore[attr-defined]
    # Prevent reading real wiki_articles_us.yaml which may contain AAPL/ABT
    monkeypatch.setattr(_data_cmd, "_load_wiki_map", lambda market: {})  # type: ignore[attr-defined]

    names = {"AAPL": "Apple Inc.", "ABT": "Abbott Laboratories"}
    monkeypatch.setattr(_data_cmd, "_get_company_name", lambda deps, t: names.get(t))  # type: ignore[attr-defined]
    monkeypatch.setattr(_data_cmd, "_get_ticker_universe", lambda config: ["AAPL", "ABT"])  # type: ignore[attr-defined]

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


def test_backtest_universe_us_excludes_tsx(monkeypatch: object) -> None:
    import application.cli as climod

    uni = climod._get_backtest_universe("us")
    assert "AAPL" in uni
    # Markets must not mix: a "us" backtest carries no TSX (.TO) names —
    # those belong only to market="ca" (see _get_backtest_universe).
    assert not any(t.endswith(".TO") for t in uni)


def test_portfolio_verdict_cli(monkeypatch: object, tmp_path: object) -> None:
    from click.testing import CliRunner

    import application.cli.portfolio_commands as _port_cmd
    from application.cli import cli

    holdings = tmp_path / "holdings.csv"  # type: ignore[operator]
    holdings.write_text("ticker,shares\nMU,25\nRIVN,80\n")

    class _UC:
        def __init__(self, *a: object, **k: object) -> None:
            pass

        def verdict_for(self, ticker: str) -> dict:
            return {
                "ticker": ticker,
                "price": 100.0,
                "verdict": "HOLD" if ticker == "MU" else "EXIT",
                "trend_intact": ticker == "MU",
                "trailing_stop": 90.0,
                "why": "test",
            }

    monkeypatch.setattr(_port_cmd, "PortfolioVerdictUseCase", _UC)

    runner = CliRunner()
    result = runner.invoke(cli, ["portfolio-verdict", "--holdings", str(holdings)])
    assert result.exit_code == 0, result.output
    assert "MU" in result.output and "HOLD" in result.output
    assert "RIVN" in result.output and "EXIT" in result.output


def test_validate_momentum_discipline_runs(monkeypatch: object) -> None:
    from click.testing import CliRunner

    import application.cli as climod
    from application.cli import cli

    class _UC:
        def __init__(self, *a: object, **k: object) -> None:
            pass

        def execute(
            self, universe: object, start: object, end: object
        ) -> dict[str, object]:
            return {
                "strategy": {
                    "sharpe": 1.1,
                    "max_drawdown": 0.2,
                    "cagr": 0.12,
                    "sortino": 1.3,
                    "equity": [1.0, 1.05, 1.1],
                },
                "buy_hold": {
                    "sharpe": 0.6,
                    "max_drawdown": 0.5,
                    "cagr": 0.10,
                    "sortino": 0.7,
                    "equity": [1.0, 0.95, 1.0],
                },
                "spy": {
                    "sharpe": 0.7,
                    "max_drawdown": 0.34,
                    "cagr": 0.11,
                    "sortino": 0.8,
                    "equity": [1.0, 0.98, 1.05],
                },
            }

        def verdict(
            self, report: object, sharpe_diff_ci_low: float
        ) -> dict[str, object]:
            return {
                "decision": "PROCEED",
                "drawdown_reduction": 0.6,
                "sharpe_diff_ci_low": sharpe_diff_ci_low,
                "beats_sharpe": True,
                "cuts_drawdown": True,
            }

    monkeypatch.setattr(climod, "MomentumExitBacktestUseCase", _UC, raising=False)
    monkeypatch.setattr(
        climod, "_get_backtest_universe", lambda m: ["AAPL", "MSFT"], raising=False
    )

    runner = CliRunner()
    result = runner.invoke(
        cli, ["validate-momentum-discipline", "--limit", "2", "--quick"]
    )
    assert result.exit_code == 0, result.output
    assert "PROCEED" in result.output or "KILL" in result.output
    assert "sharpe" in result.output.lower()


def test_holdings_risk_cli_masked_summary(monkeypatch, tmp_path):
    from click.testing import CliRunner

    import application.cli.portfolio_commands as _port_cmd
    from application.cli import cli
    from domain.discipline import Verdict
    from domain.models import PortfolioRisk, PositionRisk

    holdings = tmp_path / "h.csv"
    holdings.write_text(
        "Symbol,Quantity,Book Value (CAD),Account Type,Exchange\nMU,10,3000,TFSA,NASDAQ\n"
    )

    class _UC:
        def __init__(self, *a, **k):
            pass

        def execute(self, hold, start, end):
            pos = PositionRisk(
                ticker="MU",
                price=100.0,
                verdict=Verdict.REDUCE,
                confidence=0.8,
                trend_health=-3.0,
                vol_signal=0.5,
                relative_strength=-0.2,
                downside_to_stop=0.1,
                upside_to_recover=0.3,
                behavior_flags=("disposition_risk",),
                unrealized_pct=-0.31,
                account_type="TFSA",
                abstained=False,
                why="broke trend",
            )
            return {
                "positions": [pos],
                "portfolio": PortfolioRisk(1, 1.0, 1.0, {"REDUCE": 1}),
            }

    monkeypatch.setattr(_port_cmd, "HoldingsRiskAssessmentUseCase", _UC)

    runner = CliRunner()
    out_file = tmp_path / "detail.txt"
    log_file = tmp_path / "log.jsonl"
    # Isolate --log to tmp: never append synthetic rows to the real personal log.
    result = runner.invoke(
        cli,
        [
            "holdings-risk",
            "--holdings",
            str(holdings),
            "--out",
            str(out_file),
            "--log",
            str(log_file),
        ],
    )
    assert result.exit_code == 0, result.output
    assert "REDUCE" in result.output
    assert "MU" not in result.output
    assert out_file.exists()
    assert "MU" in out_file.read_text()
    # The forward-calibration log was written to the isolated tmp path, not the default.
    assert log_file.exists()
    assert "MU" in log_file.read_text()


def test_resolve_discipline_flags_cli(monkeypatch, tmp_path):
    from click.testing import CliRunner

    import application.cli as climod
    from application.cli import cli

    log = tmp_path / "log.jsonl"
    log.write_text(
        '{"ticker": "MU", "verdict": "REDUCE", "price": 100.0, "as_of": "2026-01-01T00:00:00+00:00"}\n'
    )
    monkeypatch.setattr(
        climod,
        "load_price_series",
        lambda t, s, e: [
            (__import__("datetime").datetime(2026, 1, 1), 100.0),
            (__import__("datetime").datetime(2026, 3, 1), 70.0),
        ],
        raising=False,
    )
    runner = CliRunner()
    result = runner.invoke(cli, ["resolve-discipline-flags", "--log", str(log)])
    assert result.exit_code == 0, result.output
    assert "resolved" in result.output.lower()
    assert "brier" in result.output.lower()


def test_backtest_discipline_flags_cli(monkeypatch, tmp_path):
    from click.testing import CliRunner

    import application.cli as climod
    from application.cli import cli

    h = tmp_path / "h.csv"
    h.write_text("Symbol,Quantity,Account Type,Exchange\nDOWN,10,TFSA,NASDAQ\n")
    monkeypatch.setattr(
        climod,
        "backtest_discipline_calibration",
        lambda *a, **k: {
            "total_verdicts": 5,
            "by_verdict": {
                "REDUCE": {
                    "n": 3,
                    "down": 3,
                    "down_rate": 1.0,
                    "mean_fwd_return": -0.05,
                }
            },
            "brier_reduce": 0.1,
            "n_reduce": 3,
        },
        raising=False,
    )
    result = CliRunner().invoke(
        cli, ["backtest-discipline-flags", "--holdings", str(h)]
    )
    assert result.exit_code == 0, result.output
    assert "REDUCE" in result.output and "Brier" in result.output
