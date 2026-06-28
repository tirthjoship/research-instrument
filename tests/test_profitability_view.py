"""Tests for profitability view-model + panel (Task 5, spec D10)."""

import inspect
from types import SimpleNamespace

from adapters.visualization.tabs.stock_analysis import profitability_view
from domain.fit import FORBIDDEN_WORDS


def _result(**info_over):
    info = {
        "grossMargins": 0.75,
        "operatingMargins": 0.62,
        "profitMargins": 0.55,
        "returnOnEquity": 1.15,
        "freeCashflow": 72e9,
        "totalRevenue": 130e9,
        "ebit": 80e9,
        "totalDebt": 9e9,
        "totalCash": 43e9,
    }
    info.update(info_over)
    return SimpleNamespace(
        info=info,
        quarterly_financials=None,
        quarterly_balance_sheet=None,
        ticker="NVDA",
    )


def test_six_levels_metrics():
    v = profitability_view.build_profitability_view(_result())
    labels = [m.label for m in v["metrics"]]
    assert len(v["metrics"]) == 6
    assert (
        any("Gross" in lbl for lbl in labels)
        and any("ROE" in lbl for lbl in labels)
        and any("ROIC" in lbl for lbl in labels)
    )


def test_fcf_margin_computed():
    v = profitability_view.build_profitability_view(_result())
    fcf = next(m for m in v["metrics"] if "FCF" in m.label)
    assert "55%" in fcf.value or "55" in fcf.value  # 72/130 = 55%


def test_roic_datagap_when_inputs_missing():
    v = profitability_view.build_profitability_view(_result(ebit=None))
    roic = next(m for m in v["metrics"] if "ROIC" in m.label)
    assert roic.value == "—"


def test_panel_renders():
    assert "Profitability" in profitability_view.build_profitability_panel(_result())


def test_no_streamlit_and_clean():
    src = inspect.getsource(profitability_view)
    assert "import streamlit" not in src
    low = src.lower()
    for w in FORBIDDEN_WORDS:
        assert w not in low
