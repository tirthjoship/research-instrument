import inspect
import json

from tests.cockpit.fake_st import FakeSt

SCREEN = {
    "as_of": "2026-06-12",
    "abstained": True,
    "universe_size": 480,
    "candidates": [
        {
            "ticker": "KO",
            "composite": 0.8,
            "trend_health": 0.5,
            "why": "cheap + quality",
            "factor_scores": [],
        },
        {
            "ticker": "NVDA",
            "composite": 0.7,
            "trend_health": 0.9,
            "why": "momentum",
            "factor_scores": [],
        },
        {
            "ticker": "JNJ",
            "composite": 0.6,
            "trend_health": 0.4,
            "why": "quality",
            "factor_scores": [],
        },
        {
            "ticker": "XOM",
            "composite": 0.5,
            "trend_health": 0.2,
            "why": "value",
            "factor_scores": [],
        },
    ],
}
SUMMARY = {
    "as_of": "2026-06-12",
    "holdings": [],
    "macro": {
        "dominant_factor": "SPY",
        "systematic_share": 0.64,
        "net_beta_by_factor": {"SPY": 1.3},
        "factors": ["SPY"],
        "flags": [],
        "coverage_holdings": 1,
        "total_holdings": 1,
        "idiosyncratic_share": 0.36,
    },
}


def _render(monkeypatch, tmp_path, screen=SCREEN):
    from adapters.visualization.cockpit import _discover

    sink: list[str] = []
    monkeypatch.setattr(_discover, "st", FakeSt(sink))
    monkeypatch.setattr(
        _discover,
        "_diversification_ranks",
        lambda cands, dom: [("KO", 0.05), ("JNJ", 0.10), ("XOM", 0.30), ("NVDA", 0.90)],
    )
    (tmp_path / "brief_summary.json").write_text(json.dumps(SUMMARY))
    if screen is not None:
        (tmp_path / "screen_2026-06-12.json").write_text(json.dumps(screen))
    (tmp_path / "holdings.csv").write_text(
        "Symbol,Quantity,Average Cost,Account Type,Exchange\nSPY,1,400,TFSA,NYSE\n"
    )
    _discover.render(
        summary_path=str(tmp_path / "brief_summary.json"),
        reports_dir=str(tmp_path),
        holdings_path=str(tmp_path / "holdings.csv"),
    )
    return " ".join(sink)


def test_feed_shows_on_abstention_with_banner_and_capped_rows(monkeypatch, tmp_path):
    out = _render(monkeypatch, tmp_path)
    assert "research starting points only" in out.lower()
    assert "KO" in out  # most diversifying leads
    assert out.count("cp-row") <= 5  # 3-5 rows cap (validation Q3)


def test_missing_screen_falls_back_gracefully(monkeypatch, tmp_path):
    out = _render(monkeypatch, tmp_path, screen=None)
    assert "no screen artifact" in out.lower()


def test_discover_source_has_no_forbidden_words():
    from adapters.visualization.cockpit import _discover
    from domain.fit import FORBIDDEN_WORDS

    src = inspect.getsource(_discover).lower()
    for word in FORBIDDEN_WORDS:
        assert word not in src, f"forbidden word {word!r} in _discover source"
