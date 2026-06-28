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


def test_no_streamlit_and_clean():
    src = inspect.getsource(vitals)
    assert "import streamlit" not in src
    low = src.lower()
    for w in FORBIDDEN_WORDS:
        assert w not in low
