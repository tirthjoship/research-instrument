import inspect
from types import SimpleNamespace

from adapters.visualization.tabs.stock_analysis import vitals
from domain.fit import FORBIDDEN_WORDS


def _result():
    return SimpleNamespace(
        peer_percentiles={"P/E": 78.0},
        info={
            "revenueGrowth": 0.69,
            "trailingPE": 52.0,
            "freeCashflow": 72e9,
            "52WeekChange": 0.42,
            "SandP52WeekChange": 0.14,
        },
        analyst_panel=SimpleNamespace(target_mean=200.0, data_gap=False),
        current_price=172.0,
        insider_transactions=[{"value": -48_000_000}],
    )


def test_view_has_six_tiles_with_required_keys():
    v = vitals.build_vitals_view(_result())
    assert len(v.tiles) == 6
    for t in v.tiles:
        assert t["label"] and t["meaning"] and t["basis"]


def test_pe_tile_amber_top_quartile():
    v = vitals.build_vitals_view(_result())
    pe = next(t for t in v.tiles if "P/E" in t["label"])
    assert pe["tone"] == "amber" and "52" in pe["value"]


def test_html_renders_six_vt_tiles_with_tooltips():
    html = vitals.build_vitals_html(vitals.build_vitals_view(_result()))
    assert html.count("sa-vt") == 6
    assert 'class="sa-grid6"' in html
    assert html.count("sa-tip") >= 6  # working tooltip on every tile


def test_datagap_tile_is_grey():
    r = _result()
    r.peer_percentiles = {}
    v = vitals.build_vitals_view(r)
    pe = next(t for t in v.tiles if "P/E" in t["label"])
    assert pe["tone"] == "grey" and pe["value"] in ("—", "n/a")


def test_insiders_q_tile_uses_latest_quarter_not_alltime_sum():
    # Same bug class fixed in ownership_view: this tile is labelled "Insiders Q"
    # ("net insider transaction value last quarter") and must match the latest
    # quarter's bucket (-$186M), not the sum across all three quarters (-$396M).
    r = _result()
    r.insider_transactions = [
        {"value": -186e6, "Start Date": "2026-06-18"},
        {"value": -120e6, "Start Date": "2026-03-15"},
        {"value": -90e6, "Start Date": "2025-12-10"},
    ]
    v = vitals.build_vitals_view(r)
    tile = next(t for t in v.tiles if "Insiders" in t["label"])
    assert tile["value"] == "-186M"


def test_canadian_ticker_target_and_fcf_tiles_show_cad_symbol():
    """A TSX-suffixed ticker's Price-vs-target and Free-cash-flow tiles must
    show C$, not bare $ — bare $ would misrepresent CAD amounts as USD."""
    r = _result()
    r.ticker = "RY.TO"
    v = vitals.build_vitals_view(r)
    tgt = next(t for t in v.tiles if "tgt" in t["label"])
    fcf = next(t for t in v.tiles if "Free cash flow" in t["label"])
    assert tgt["value"].startswith("C$")
    assert fcf["value"].startswith("C$")
    assert "$" not in tgt["value"].replace("C$", "")
    assert "$" not in fcf["value"].replace("C$", "")


def test_no_streamlit_and_clean():
    src = inspect.getsource(vitals)
    assert "import streamlit" not in src
    low = src.lower()
    for w in FORBIDDEN_WORDS:
        assert w not in low
