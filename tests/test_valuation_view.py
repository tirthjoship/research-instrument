import inspect
from types import SimpleNamespace

from adapters.visualization.tabs.stock_analysis import valuation_view
from domain.fit import FORBIDDEN_WORDS


def _result(**over):
    info = {
        "trailingPE": 52.0,
        "forwardPE": 34.0,
        "pegRatio": 0.75,
        "priceToSalesTrailing12Months": 28.0,
        "enterpriseToEbitda": 45.0,
        "marketCap": 4.2e12,
        "freeCashflow": 72e9,
    }
    info.update(over.pop("info", {}))
    base = dict(
        info=info,
        peer_data=[{"ticker": "NVDA", "pe": 52.0}, {"ticker": "AMD", "pe": 38.0}],
        peer_percentiles={"P/E": 78.0},
        ticker="NVDA",
    )
    base.update(over)
    return SimpleNamespace(**base)


def test_view_has_six_multiples():
    v = valuation_view.build_valuation_view(_result())
    labels = [m.label for m in v["metrics"]]
    assert len(v["metrics"]) == 6
    assert any("P/E" in lbl for lbl in labels) and any("PEG" in lbl for lbl in labels)
    assert any("EV/EBITDA" in lbl for lbl in labels) and any(
        "P/FCF" in lbl for lbl in labels
    )


def test_pfcf_computed():
    v = valuation_view.build_valuation_view(_result())
    pfcf = next(m for m in v["metrics"] if "P/FCF" in m.label)
    # 4.2e12 / 72e9 = 58.3 -> ~58
    assert "58" in pfcf.value


def test_peg_under_one_is_green():
    v = valuation_view.build_valuation_view(_result())
    peg = next(m for m in v["metrics"] if "PEG" in m.label)
    assert peg.tone == "green"


def test_missing_multiple_is_datagap():
    r = _result(info={"trailingPE": None, "freeCashflow": None})
    v = valuation_view.build_valuation_view(r)
    pe = next(m for m in v["metrics"] if m.label.startswith("P/E ttm"))
    assert pe.value == "—" and pe.tone == "grey"


def test_low_percentile_multiple_also_amber():
    r = _result(peer_percentiles={"P/E": 12.0})
    v = valuation_view.build_valuation_view(r)
    pe = next(m for m in v["metrics"] if m.label.startswith("P/E ttm"))
    assert pe.tone == "amber"


def test_panel_renders_with_chips_strip_and_drill():
    html = valuation_view.build_valuation_panel(_result())
    assert "sa-pnl" in html and "Valuation" in html
    assert "sa-chip" in html and html.count("sa-tip") >= 3
    assert "sa-drill" in html


def test_no_streamlit_and_clean():
    src = inspect.getsource(valuation_view)
    assert "import streamlit" not in src
    low = src.lower()
    for w in FORBIDDEN_WORDS:
        assert w not in low
