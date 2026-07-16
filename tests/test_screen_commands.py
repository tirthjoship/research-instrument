"""Tests for application/cli/screen_commands.py — screen-candidates CLI."""

from __future__ import annotations


def _fake_use_case_factory():
    """Build a fake evidence-screen use case with real ScreenResult-shaped output.

    `screen_candidates` accesses `result.candidates`, `result.regime`, etc. by
    attribute (not dict key), and also calls `uc.surface_calls(...)` — so the
    fake must mirror the real EvidenceScreenUseCase's returned type/interface,
    not just its abstained/universe_size keys.
    """
    from domain.screen_models import ScreenResult

    class _FakeUseCase:
        def run(self, universe, as_of, top_n):
            return ScreenResult(
                as_of=as_of,
                candidates=(),
                universe_size=len(universe),
                regime="neutral",
                scorecard_ref=None,
                abstained=True,
            )

        def surface_calls(self, top_result, as_of_dt, store):
            return None

    return _FakeUseCase()


def test_screen_candidates_market_option_defaults_to_us(monkeypatch, tmp_path):
    from click.testing import CliRunner

    from application.cli import screen_commands as sc

    captured: dict[str, object] = {}

    def fake_build_dependencies(market, use_cache=False):
        captured["market"] = market
        return {"config": {"universe": {"ticker_files": []}}, "store": None}

    monkeypatch.setattr(sc, "_build_dependencies", fake_build_dependencies)
    monkeypatch.setattr(sc, "_get_ticker_universe", lambda config: ["AAPL"])
    monkeypatch.setattr(
        sc, "_build_evidence_screen", lambda deps: _fake_use_case_factory()
    )

    runner = CliRunner()
    result = runner.invoke(sc.cli, ["screen-candidates", "--report-dir", str(tmp_path)])

    assert result.exit_code == 0, result.output
    assert captured["market"] == "us"


def test_screen_candidates_market_option_ca(monkeypatch, tmp_path):
    from click.testing import CliRunner

    from application.cli import screen_commands as sc

    captured: dict[str, object] = {}

    def fake_build_dependencies(market, use_cache=False):
        captured["market"] = market
        return {"config": {"universe": {"ticker_files": []}}, "store": None}

    monkeypatch.setattr(sc, "_build_dependencies", fake_build_dependencies)
    monkeypatch.setattr(sc, "_get_ticker_universe", lambda config: ["RY"])
    monkeypatch.setattr(
        sc, "_build_evidence_screen", lambda deps: _fake_use_case_factory()
    )

    runner = CliRunner()
    result = runner.invoke(
        sc.cli,
        ["screen-candidates", "--market", "ca", "--report-dir", str(tmp_path)],
    )

    assert result.exit_code == 0, result.output
    assert captured["market"] == "ca"

    import json
    from pathlib import Path as _Path

    written = list(_Path(tmp_path).glob("screen_*.json"))
    assert len(written) == 1
    payload = json.loads(written[0].read_text())
    assert payload["market"] == "ca"
