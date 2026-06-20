# tests/test_cli_weekly_brief.py
from __future__ import annotations

import json
import os

import pytest
from click.testing import CliRunner

from application import cli as cli_mod
from application.cli import brief_commands as _brief_cmd
from application.holdings_reader import Holding
from application.weekly_brief_use_case import RegimeReadUseCase, WeeklyBriefUseCase
from domain.case_models import CaseContext, CaseResult
from domain.discipline import Verdict
from domain.models import PortfolioRisk, PositionRisk
from domain.screen_models import FactorScore, ScreenCandidate, ScreenLabel, ScreenResult


def _fs():  # type: ignore[no-untyped-def]
    return (
        FactorScore("momentum", 1.1, 0.82, 0.27),
        FactorScore("revision", 0.0, 0.0, 0.0),
        FactorScore("quality", 0.0, 0.0, 0.0),
        FactorScore("value", 0.0, 0.0, 0.0),
    )


class _FakeScreen:
    def run(self, universe: list[str], as_of: str, top_n: int = 10) -> ScreenResult:  # type: ignore[no-untyped-def]
        return ScreenResult(
            as_of,
            (
                ScreenCandidate(
                    "AAPL", 0.42, _fs(), 1.3, "momentum", ScreenLabel.RESEARCH_ONLY
                ),
            ),
            500,
            "NEUTRAL",
            None,
            False,
        )


class _FakeHoldingsRisk:
    def execute(self, holdings: list[Holding], start: object, end: object) -> dict[str, object]:  # type: ignore[no-untyped-def]
        return {
            "positions": [
                PositionRisk(
                    "RIVN",
                    10.0,
                    Verdict.REDUCE,
                    0.7,
                    -1.2,
                    0.0,
                    -0.1,
                    0.4,
                    0.1,
                    ("broken_trend",),
                    -0.45,
                    "Margin",
                    False,
                    "broken trend",
                ),
            ],
            "portfolio": PortfolioRisk(1, 1.0, 0.10, {"REDUCE": 1}),
        }


def test_weekly_brief_cli_masks_stdout_and_writes_gitignored_file(tmp_path, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    out_file = tmp_path / "weekly_brief.md"
    holdings_csv = tmp_path / "holdings.csv"
    holdings_csv.write_text(
        "symbol,quantity,book value (cad),exchange,account type\nRIVN,10,500,NASDAQ,Margin\n"
    )

    def _fake_build(
        market: str, holdings: list[Holding], report_dir: str
    ) -> tuple[WeeklyBriefUseCase, list[str]]:  # noqa: ANN001
        uc = WeeklyBriefUseCase(
            screen=_FakeScreen(),
            holdings_risk=_FakeHoldingsRisk(),
            regime_reader=RegimeReadUseCase(
                vix_provider=lambda: 20.0, spy_trend_provider=lambda: 0.1
            ),
            screen_label_fn=lambda rd: ScreenLabel.RESEARCH_ONLY,
            cluster_peers_fn=lambda t: [],
            screen_scorecard_fn=lambda: (None, None, 0, False),
            discipline_scorecard_fn=lambda: (0.58, 5462, "PENDING"),
        )
        return uc, ["AAPL", "RIVN"]

    monkeypatch.setattr(_brief_cmd, "_build_weekly_brief", _fake_build)

    runner = CliRunner()
    result = runner.invoke(
        cli_mod.cli,
        ["weekly-brief", "--holdings", str(holdings_csv), "--out", str(out_file)],
    )
    assert result.exit_code == 0, result.output
    # stdout is masked: no holding ticker, no P&L.
    assert "RIVN" not in result.output
    assert "HOLDINGS (masked)" in result.output
    # full markdown written, and it DOES contain the holding ticker.
    assert out_file.exists()
    assert "RIVN" in out_file.read_text()


def test_weekly_brief_default_out_is_gitignored_personal_dir() -> None:
    # The default --out must live under data/personal/ (gitignored).
    params = {p.name: p for p in cli_mod.weekly_brief.params}
    assert params["out"].default.startswith("data/personal/")


# ---------------------------------------------------------------------------
# D3 — cited-case prefetch opt-in (--cite-cases)
# ---------------------------------------------------------------------------


class _FakeCaseSummarizer:
    """Instant fake summarizer — no sleep, no network."""

    def __init__(self) -> None:
        self.calls: list[CaseContext] = []

    def summarize_case(self, ctx: CaseContext) -> CaseResult:
        self.calls.append(ctx)
        return CaseResult(in_favor=(), to_watch=(), data_gap=True)


def _fake_select_summarizer(fake: _FakeCaseSummarizer) -> object:
    return fake


def test_cite_cases_flag_writes_cache(
    tmp_path: object, monkeypatch: pytest.MonkeyPatch
) -> None:
    """--cite-cases prefetches all holding tickers and writes cited_cases.json."""
    assert isinstance(tmp_path, os.PathLike)
    out_file = tmp_path / "weekly_brief.md"
    holdings_csv = tmp_path / "holdings.csv"
    holdings_csv.write_text(
        "symbol,quantity,book value (cad),exchange,account type\nRIVN,10,500,NASDAQ,Margin\n"
    )
    cache_path = str(tmp_path / "cited_cases.json")

    def _fake_build(
        market: str, holdings: list[Holding], report_dir: str
    ) -> tuple[WeeklyBriefUseCase, list[str]]:
        uc = WeeklyBriefUseCase(
            screen=_FakeScreen(),
            holdings_risk=_FakeHoldingsRisk(),
            regime_reader=RegimeReadUseCase(
                vix_provider=lambda: 20.0, spy_trend_provider=lambda: 0.1
            ),
            screen_label_fn=lambda rd: ScreenLabel.RESEARCH_ONLY,
            cluster_peers_fn=lambda t: [],
            screen_scorecard_fn=lambda: (None, None, 0, False),
            discipline_scorecard_fn=lambda: (0.58, 5462, "PENDING"),
        )
        return uc, ["AAPL", "RIVN"]

    fake_summarizer = _FakeCaseSummarizer()

    monkeypatch.setattr(_brief_cmd, "_build_weekly_brief", _fake_build)
    # Patch the select_case_summarizer used inside the CLI
    import application.card_loading as cl_mod

    monkeypatch.setattr(cl_mod, "select_case_summarizer", lambda: fake_summarizer)
    # Redirect cache path
    import application.case_cache as cc_mod

    monkeypatch.setattr(cc_mod, "CITED_CASES_PATH", cache_path)

    runner = CliRunner()
    result = runner.invoke(
        cli_mod.cli,
        [
            "weekly-brief",
            "--holdings",
            str(holdings_csv),
            "--out",
            str(out_file),
            "--cite-cases",
        ],
    )
    assert result.exit_code == 0, result.output

    # Cache file must exist and contain the holding ticker(s)
    assert os.path.exists(cache_path), "cited_cases.json must be written"
    raw = json.loads(open(cache_path).read())
    assert "cases" in raw
    # RIVN is the holding — it must appear in the cache
    assert "RIVN" in raw["cases"]


def test_no_cite_cases_skips_prefetch(
    tmp_path: object, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Without --cite-cases, the summarizer is never called (no sleep, no ping)."""
    assert isinstance(tmp_path, os.PathLike)
    out_file = tmp_path / "weekly_brief.md"
    holdings_csv = tmp_path / "holdings.csv"
    holdings_csv.write_text(
        "symbol,quantity,book value (cad),exchange,account type\nRIVN,10,500,NASDAQ,Margin\n"
    )

    def _fake_build(
        market: str, holdings: list[Holding], report_dir: str
    ) -> tuple[WeeklyBriefUseCase, list[str]]:
        uc = WeeklyBriefUseCase(
            screen=_FakeScreen(),
            holdings_risk=_FakeHoldingsRisk(),
            regime_reader=RegimeReadUseCase(
                vix_provider=lambda: 20.0, spy_trend_provider=lambda: 0.1
            ),
            screen_label_fn=lambda rd: ScreenLabel.RESEARCH_ONLY,
            cluster_peers_fn=lambda t: [],
            screen_scorecard_fn=lambda: (None, None, 0, False),
            discipline_scorecard_fn=lambda: (0.58, 5462, "PENDING"),
        )
        return uc, ["AAPL", "RIVN"]

    fake_summarizer = _FakeCaseSummarizer()
    monkeypatch.setattr(_brief_cmd, "_build_weekly_brief", _fake_build)
    import application.card_loading as cl_mod
    import application.risk_second_opinion as _rso_mod

    monkeypatch.setattr(cl_mod, "select_case_summarizer", lambda: fake_summarizer)
    # build_risk_second_opinion is a cache-warming side-effect unrelated to --cite-cases;
    # stub it out so it doesn't call the fake summarizer and pollute the assertion.
    monkeypatch.setattr(_rso_mod, "build_risk_second_opinion", lambda *a, **k: None)

    runner = CliRunner()
    result = runner.invoke(
        cli_mod.cli,
        [
            "weekly-brief",
            "--holdings",
            str(holdings_csv),
            "--out",
            str(out_file),
            # NOTE: no --cite-cases flag → prefetch skipped
        ],
    )
    assert result.exit_code == 0, result.output
    assert (
        fake_summarizer.calls == []
    ), "summarizer must not be called without --cite-cases"


def test_cite_cases_progress_line_in_output(
    tmp_path: object, monkeypatch: pytest.MonkeyPatch
) -> None:
    """--cite-cases must echo a progress line for each ticker analysed."""
    assert isinstance(tmp_path, os.PathLike)
    out_file = tmp_path / "weekly_brief.md"
    holdings_csv = tmp_path / "holdings.csv"
    holdings_csv.write_text(
        "symbol,quantity,book value (cad),exchange,account type\nRIVN,10,500,NASDAQ,Margin\n"
    )
    cache_path = str(tmp_path / "cited_cases.json")

    def _fake_build(
        market: str, holdings: list[Holding], report_dir: str
    ) -> tuple[WeeklyBriefUseCase, list[str]]:
        uc = WeeklyBriefUseCase(
            screen=_FakeScreen(),
            holdings_risk=_FakeHoldingsRisk(),
            regime_reader=RegimeReadUseCase(
                vix_provider=lambda: 20.0, spy_trend_provider=lambda: 0.1
            ),
            screen_label_fn=lambda rd: ScreenLabel.RESEARCH_ONLY,
            cluster_peers_fn=lambda t: [],
            screen_scorecard_fn=lambda: (None, None, 0, False),
            discipline_scorecard_fn=lambda: (0.58, 5462, "PENDING"),
        )
        return uc, ["AAPL", "RIVN"]

    fake_summarizer = _FakeCaseSummarizer()
    monkeypatch.setattr(_brief_cmd, "_build_weekly_brief", _fake_build)
    import application.card_loading as cl_mod

    monkeypatch.setattr(cl_mod, "select_case_summarizer", lambda: fake_summarizer)
    import application.case_cache as cc_mod

    monkeypatch.setattr(cc_mod, "CITED_CASES_PATH", cache_path)

    runner = CliRunner()
    result = runner.invoke(
        cli_mod.cli,
        [
            "weekly-brief",
            "--holdings",
            str(holdings_csv),
            "--out",
            str(out_file),
            "--cite-cases",
        ],
    )
    assert result.exit_code == 0, result.output
    # At least one "Analysing" line must appear
    assert "Analysing" in result.output
