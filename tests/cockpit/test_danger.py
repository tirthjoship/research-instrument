import json

from tests.cockpit.fake_st import FakeSt

SUMMARY = {
    "as_of": "2026-06-12",
    "holdings": [],
    "concentration": [],
    "scorecard": {
        "discipline_window": "2026-04-15..2026-07-15",
        "discipline_n": 7,
        "discipline_gate_status": "ACCRUING",
    },
    "macro": {
        "factors": ["SPY", "TLT"],
        "net_beta_by_factor": {"SPY": 1.37, "TLT": -0.2},
        "systematic_share": 0.64,
        "idiosyncratic_share": 0.36,
        "dominant_factor": "SPY",
        "flags": ["FACTOR_DOMINANCE"],
        "coverage_holdings": 5,
        "total_holdings": 5,
    },
}


def _render(monkeypatch, tmp_path, summary):
    from adapters.visualization.cockpit import _danger

    sink: list[str] = []
    monkeypatch.setattr(_danger, "st", FakeSt(sink))
    p = tmp_path / "brief_summary.json"
    if summary is not None:
        p.write_text(json.dumps(summary))
    log = tmp_path / "log.jsonl"
    _danger.render(summary_path=str(p), discipline_log_path=str(log))
    return " ".join(sink)


def test_danger_shows_dominant_bet_and_gate(monkeypatch, tmp_path):
    monkeypatch.setattr("adapters.visualization.tabs.risk.render", lambda **k: None)
    out = _render(monkeypatch, tmp_path, SUMMARY)
    assert "64%" in out  # systematic share
    assert "SPY" in out and "1.37" in out
    assert "ACCRUING" in out  # gate status
    assert "EXPANDER" in out  # risk drill-down reachable


def test_danger_degrades_without_summary(monkeypatch, tmp_path):
    out = _render(monkeypatch, tmp_path, None)
    assert "No weekly brief yet" in out
