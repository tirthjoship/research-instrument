"""CLI tests for screen-candidates and backtest-screen commands.

These are fast unit tests — the use cases are monkeypatched so no yfinance
or other live network calls are made.
"""

from __future__ import annotations

import json

import pytest
from click.testing import CliRunner

from application.cli import cli
from application.screen_backtest_use_case import ScreenVerdict
from domain.screen_models import ScreenCandidate, ScreenLabel, ScreenResult

# ---------------------------------------------------------------------------
# Helpers / fakes
# ---------------------------------------------------------------------------


def _fake_factor_scores() -> tuple:  # type: ignore[type-arg]
    from domain.screen_models import FactorScore

    return (
        FactorScore("momentum", 0.5, 0.7, 0.125),
        FactorScore("revision", 0.3, 0.6, 0.075),
        FactorScore("quality", 0.2, 0.5, 0.05),
        FactorScore("value", 0.1, 0.4, 0.025),
    )


def _make_screen_result(tickers: list[str] = ("AAPL", "MSFT", "NVDA")) -> ScreenResult:
    cands = tuple(
        ScreenCandidate(
            ticker=t,
            composite=float(i),
            factor_scores=_fake_factor_scores(),
            trend_health=0.4,
            why=f"why-{t}",
            label=ScreenLabel.RESEARCH_ONLY,
        )
        for i, t in enumerate(reversed(tickers))
    )
    return ScreenResult(
        as_of="2026-06-08",
        candidates=cands,
        universe_size=len(tickers),
        regime="NEUTRAL",
        scorecard_ref=None,
    )


# ---------------------------------------------------------------------------
# Task 7a: screen-candidates
# ---------------------------------------------------------------------------


def test_screen_candidates_masked_summary(
    tmp_path: object, monkeypatch: pytest.MonkeyPatch
) -> None:
    from application import evidence_screen_use_case as esc_module

    fake_result = _make_screen_result()

    class FakeUseCase:
        def run(self, universe: list[str], as_of: str, top_n: int = 10) -> ScreenResult:
            return fake_result

        def surface_calls(self, result: object, **kw: object) -> list[object]:
            return []

    monkeypatch.setattr(esc_module, "EvidenceScreenUseCase", lambda **kw: FakeUseCase())  # type: ignore[attr-defined]

    runner = CliRunner()
    res = runner.invoke(
        cli, ["screen-candidates", "--top", "10", "--report-dir", str(tmp_path)]
    )
    assert res.exit_code == 0, res.output
    assert "candidates" in res.output.lower()
    report_files = list(tmp_path.glob("screen_*.json"))  # type: ignore[union-attr]
    assert report_files, "Expected a screen_<date>.json report file"


def test_screen_candidates_writes_full_distribution(
    tmp_path: object, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The JSON must contain ALL candidates (full distribution), not just top-N.

    The fake use case returns a result whose candidate count (5) exceeds --top (2).
    It honors the top_n argument by returning ALL eligible candidates (full universe),
    and the CLI must NOT silently truncate them in the JSON.
    """
    from application import evidence_screen_use_case as esc_module

    UNIVERSE = ["AAPL", "MSFT", "NVDA", "GOOG", "META"]

    class FakeUseCase:
        """Fake that honours top_n like rank_universe does for the FULL universe."""

        def run(self, universe: list[str], as_of: str, top_n: int = 10) -> ScreenResult:
            # Return ALL tickers regardless of top_n — simulates the full distribution.
            # The CLI is responsible for passing top_n = len(universe) here.
            return _make_screen_result(UNIVERSE)

        def surface_calls(self, result: object, **kw: object) -> list[object]:
            return []

    monkeypatch.setattr(esc_module, "EvidenceScreenUseCase", lambda **kw: FakeUseCase())  # type: ignore[attr-defined]

    runner = CliRunner()
    res = runner.invoke(
        cli, ["screen-candidates", "--top", "2", "--report-dir", str(tmp_path)]
    )
    assert res.exit_code == 0, res.output

    report_files = list(tmp_path.glob("screen_*.json"))  # type: ignore[union-attr]
    assert report_files
    data = json.loads(report_files[0].read_text())
    # full distribution — all 5 candidates, even though --top 2
    assert len(data["candidates"]) == len(UNIVERSE), (
        f"JSON must contain all {len(UNIVERSE)} candidates, not just top-2; "
        f"got {len(data['candidates'])}"
    )
    # The JSON length is GREATER than top=2 (proving no silent top-N cut)
    assert len(data["candidates"]) > 2


def test_screen_candidates_stdout_masked(
    tmp_path: object, monkeypatch: pytest.MonkeyPatch
) -> None:
    """stdout must show counts / label distribution, NOT individual ticker conviction scores."""
    from application import evidence_screen_use_case as esc_module

    fake_result = _make_screen_result()

    class FakeUseCase:
        def run(self, universe: list[str], as_of: str, top_n: int = 10) -> ScreenResult:
            return fake_result

        def surface_calls(self, result: object, **kw: object) -> list[object]:
            return []

    monkeypatch.setattr(esc_module, "EvidenceScreenUseCase", lambda **kw: FakeUseCase())  # type: ignore[attr-defined]

    runner = CliRunner()
    res = runner.invoke(
        cli, ["screen-candidates", "--top", "10", "--report-dir", str(tmp_path)]
    )
    assert res.exit_code == 0, res.output
    # Must show candidate count
    assert any(char.isdigit() for char in res.output)
    # Individual composite scores should NOT appear (would be floats like 2.0000)
    # stdout should NOT contain per-ticker lines like "AAPL   2.00"
    output_lines = res.output.strip().split("\n")
    # All lines are summary lines: no line should start with a ticker symbol
    for line in output_lines:
        stripped = line.strip()
        # A per-ticker disclosure would start with the ticker then a space
        assert not (
            stripped.startswith("AAPL ")
            or stripped.startswith("MSFT ")
            or stripped.startswith("NVDA ")
        ), f"Stdout must be masked, found possible ticker line: {line!r}"


def test_screen_candidates_json_contains_abstained(
    tmp_path: object, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The JSON report must contain an 'abstained' field surfacing the thin-coverage flag."""
    from application import evidence_screen_use_case as esc_module

    fake_result = _make_screen_result()

    class FakeUseCase:
        def run(self, universe: list[str], as_of: str, top_n: int = 10) -> ScreenResult:
            return fake_result

        def surface_calls(self, result: object, **kw: object) -> list[object]:
            return []

    monkeypatch.setattr(esc_module, "EvidenceScreenUseCase", lambda **kw: FakeUseCase())  # type: ignore[attr-defined]

    runner = CliRunner()
    res = runner.invoke(
        cli, ["screen-candidates", "--top", "10", "--report-dir", str(tmp_path)]
    )
    assert res.exit_code == 0, res.output
    report_files = list(tmp_path.glob("screen_*.json"))  # type: ignore[union-attr]
    assert report_files
    data = json.loads(report_files[0].read_text())
    assert "abstained" in data, "JSON must contain 'abstained' field"


# ---------------------------------------------------------------------------
# Task 7b: backtest-screen
# ---------------------------------------------------------------------------


def test_backtest_screen_writes_ic_report(
    tmp_path: object, monkeypatch: pytest.MonkeyPatch
) -> None:
    from application import screen_backtest_use_case as sbu_module

    class FakeBacktestUC:
        def run(self, panels: list[dict]) -> ScreenVerdict:  # type: ignore[type-arg]
            return ScreenVerdict(decision="PASS", mean_ic=0.035, n_dates=60)

    monkeypatch.setattr(sbu_module, "ScreenBacktestUseCase", lambda: FakeBacktestUC())  # type: ignore[attr-defined]

    runner = CliRunner()
    res = runner.invoke(cli, ["backtest-screen", "--report-dir", str(tmp_path)])
    assert res.exit_code == 0, res.output
    ic_files = list(tmp_path.glob("screen_ic_*.json"))  # type: ignore[union-attr]
    assert ic_files, "Expected a screen_ic_<date>.json report"


def test_backtest_screen_prints_verdict(
    tmp_path: object, monkeypatch: pytest.MonkeyPatch
) -> None:
    from application import screen_backtest_use_case as sbu_module

    for decision in ("PASS", "INCONCLUSIVE", "HALT"):

        class FakeBacktestUC:
            _d = decision

            def run(self, panels: list[dict]) -> ScreenVerdict:  # type: ignore[type-arg]
                return ScreenVerdict(decision=self._d, mean_ic=0.01, n_dates=5)

        monkeypatch.setattr(sbu_module, "ScreenBacktestUseCase", lambda: FakeBacktestUC())  # type: ignore[attr-defined]

        runner = CliRunner()
        res = runner.invoke(cli, ["backtest-screen", "--report-dir", str(tmp_path)])
        assert res.exit_code == 0, res.output
        assert decision in res.output
