"""Tests for profitability view-model + panel (Task 5, spec D10)."""

import inspect
from types import SimpleNamespace

import pandas as pd

from adapters.visualization.tabs.stock_analysis import profitability_view
from domain.fit import FORBIDDEN_WORDS


def _margin_df(gross_newest_first: list[float]) -> pd.DataFrame:
    """quarterly_financials with Revenue=100 so Gross Profit == margin*100."""
    cols = [f"2025-{m:02d}-01" for m in range(len(gross_newest_first), 0, -1)]
    return pd.DataFrame(
        {
            c: {
                "Total Revenue": 100.0,
                "Gross Profit": g * 100.0,
                "Operating Income": g * 80.0,
            }
            for c, g in zip(cols, gross_newest_first)
        }
    )


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


def test_margin_trend_axis_is_percent_not_fraction():
    # newest-first 0.75..0.60 -> chronological rising to 0.75; axis must read 75%, not 0.75%
    result = _result()
    result.quarterly_financials = _margin_df([0.75, 0.72, 0.70, 0.66, 0.63, 0.60])
    html = profitability_view.build_profitability_panel(result)
    assert "75%" in html and "0.75%" not in html


def test_margins_widening_chip_green():
    result = _result()
    result.quarterly_financials = _margin_df([0.75, 0.72, 0.70, 0.66, 0.63, 0.60])
    v = profitability_view.build_profitability_view(result)
    assert "WIDENING" in v["chips"] and "t-green" in v["chips"]


def test_margins_narrowing_chip_amber():
    result = _result()
    result.quarterly_financials = _margin_df([0.60, 0.63, 0.66, 0.70, 0.72, 0.75])
    v = profitability_view.build_profitability_view(result)
    assert "NARROWING" in v["chips"] and "t-amber" in v["chips"]


def test_panel_renders():
    assert "Profitability" in profitability_view.build_profitability_panel(_result())


def test_no_streamlit_and_clean():
    src = inspect.getsource(profitability_view)
    assert "import streamlit" not in src
    low = src.lower()
    for w in FORBIDDEN_WORDS:
        assert w not in low
