import json

from tests.cockpit.fake_st import FakeSt

CUR = {
    "as_of": "2026-06-12T00:00:00",
    "holdings": [
        {
            "ticker": "ARKK",
            "verdict": "TRIM",
            "unrealized_pct": -10.0,
            "trend_state": "broken",
            "why": "x",
        },
        {
            "ticker": "AAPL",
            "verdict": "HOLD",
            "unrealized_pct": 9.0,
            "trend_state": "uptrend",
            "why": "y",
        },
    ],
}
PREV = {
    "as_of": "2026-06-05T00:00:00",
    "holdings": [
        {
            "ticker": "ARKK",
            "verdict": "HOLD",
            "unrealized_pct": -6.0,
            "trend_state": "uptrend",
            "why": "x",
        },
        {
            "ticker": "AAPL",
            "verdict": "HOLD",
            "unrealized_pct": 7.0,
            "trend_state": "uptrend",
            "why": "y",
        },
    ],
}

HOLDINGS_CSV = "Symbol,Quantity,Average Cost,Account Type,Exchange\nARKK,10,50,TFSA,NYSE\nAAPL,5,150,TFSA,NASDAQ\n"


def _setup(tmp_path, with_prev):
    sp = tmp_path / "brief_summary.json"
    sp.write_text(json.dumps(CUR))
    hp = tmp_path / "holdings.csv"
    hp.write_text(HOLDINGS_CSV)
    hist = tmp_path / "hist"
    hist.mkdir()
    (hist / "brief_2026-06-12.json").write_text(json.dumps(CUR))
    if with_prev:
        (hist / "brief_2026-06-05.json").write_text(json.dumps(PREV))
    return sp, hp, tmp_path / "adh.jsonl", hist


def _render(monkeypatch, tmp_path, with_prev):
    from adapters.visualization.cockpit import _retro

    sink: list[str] = []
    monkeypatch.setattr(_retro, "st", FakeSt(sink))
    monkeypatch.setattr(
        _retro,
        "fetch_week_changes",
        lambda tickers: {"ARKK": -3.0, "AAPL": 2.0, "SPY": 1.0},
    )
    sp, hp, ap, hist = _setup(tmp_path, with_prev)
    _retro.render(
        summary_path=str(sp),
        holdings_path=str(hp),
        adherence_log_path=str(ap),
        history_dir=str(hist),
    )
    return " ".join(sink)


def test_retro_shows_flips_and_book_vs_spy(monkeypatch, tmp_path):
    out = _render(monkeypatch, tmp_path, with_prev=True)
    assert "ARKK" in out and "HOLD" in out and "TRIM" in out  # the flip
    assert "SPY" in out  # factual comparison present


def test_retro_first_week_degrades(monkeypatch, tmp_path):
    out = _render(monkeypatch, tmp_path, with_prev=False)
    assert "first week" in out.lower()
