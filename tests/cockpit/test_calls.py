import json

from tests.cockpit.fake_st import FakeSt

SUMMARY = {
    "as_of": "2026-06-12T00:00:00",
    "holdings": [
        {
            "ticker": "ARKK",
            "verdict": "REDUCE",
            "unrealized_pct": -12.0,
            "trend_state": "broken",
            "why": "trend broken, momentum negative",
        },
        {
            "ticker": "AAPL",
            "verdict": "HOLD",
            "unrealized_pct": 8.0,
            "trend_state": "uptrend",
            "why": "intact uptrend",
        },
    ],
}

HOLDINGS_CSV = "Symbol,Quantity,Average Cost,Account Type,Exchange\nARKK,10,50,TFSA,NYSE\nAAPL,5,150,TFSA,NASDAQ\n"


def _setup(tmp_path):
    sp = tmp_path / "brief_summary.json"
    sp.write_text(json.dumps(SUMMARY))
    hp = tmp_path / "holdings.csv"
    hp.write_text(HOLDINGS_CSV)
    return sp, hp, tmp_path / "log.jsonl", tmp_path / "hist"


def test_calls_render_verdict_cards(monkeypatch, tmp_path):
    from adapters.visualization.cockpit import _calls

    sink: list[str] = []
    monkeypatch.setattr(_calls, "st", FakeSt(sink))
    sp, hp, lp, hist = _setup(tmp_path)
    _calls.render(
        summary_path=str(sp),
        holdings_path=str(hp),
        discipline_log_path=str(lp),
        history_dir=str(hist),
    )
    out = " ".join(sink)
    assert "ARKK" in out and "REDUCE" in out and "trend broken" in out
    assert "AAPL" in out and "HOLD" in out


def test_confirm_writes_log_once_and_snapshots(monkeypatch, tmp_path):
    from adapters.visualization.cockpit import _calls
    from application.discipline_log import read_assessments

    sp, hp, lp, hist = _setup(tmp_path)
    monkeypatch.setattr(
        _calls,
        "fetch_prices",
        lambda tickers: {t: {"price": 100.0, "change_pct": 0.0} for t in tickers},
    )
    _calls.confirm_and_log(
        summary=json.loads(sp.read_text()),
        holdings_path=str(hp),
        discipline_log_path=str(lp),
        history_dir=str(hist),
    )
    rows = read_assessments(str(lp))
    assert {r["ticker"] for r in rows} == {"ARKK", "AAPL"}
    assert rows[0]["as_of"] == "2026-06-12T00:00:00"
    assert rows[0]["quantity"] in (10.0, 5.0)
    assert (hist / "brief_2026-06-12.json").exists()
    # idempotent: second confirm is a no-op
    _calls.confirm_and_log(
        summary=json.loads(sp.read_text()),
        holdings_path=str(hp),
        discipline_log_path=str(lp),
        history_dir=str(hist),
    )
    assert len(read_assessments(str(lp))) == 2
