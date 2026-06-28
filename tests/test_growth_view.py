# tests/test_growth_view.py
import inspect
from types import SimpleNamespace

import pandas as pd

from adapters.visualization.tabs.stock_analysis import growth_view
from domain.fit import FORBIDDEN_WORDS


def _df() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "2025-03-31": {"Total Revenue": 26e9, "Net Income": 14e9},
            "2024-12-31": {"Total Revenue": 22e9, "Net Income": 12e9},
            "2024-09-30": {"Total Revenue": 18e9, "Net Income": 9e9},
        }
    )


def _result(qf: pd.DataFrame | None = None) -> SimpleNamespace:
    return SimpleNamespace(
        info={"revenueGrowth": 0.69, "earningsGrowth": 0.82},
        quarterly_financials=qf if qf is not None else _df(),
        ticker="NVDA",
    )


def test_rev_and_eps_yoy_present_green() -> None:
    v = growth_view.build_growth_view(_result())
    rev = next(m for m in v["metrics"] if "Rev YoY" in m.label)
    assert "69" in rev.value and rev.tone == "green"


def test_unavailable_metrics_are_datagap() -> None:
    v = growth_view.build_growth_view(_result())
    cagr = next(m for m in v["metrics"] if "CAGR" in m.label)
    assert cagr.value == "—" and cagr.tone == "grey"


def test_handles_missing_dataframe() -> None:
    v = growth_view.build_growth_view(_result(qf=None))  # None DF
    assert isinstance(v["metrics"], list) and len(v["metrics"]) == 6


def test_panel_renders() -> None:
    html = growth_view.build_growth_panel(_result())
    assert "sa-pnl" in html and "Growth" in html and "sa-drill" in html


def test_no_streamlit_and_clean() -> None:
    src = inspect.getsource(growth_view)
    assert "import streamlit" not in src
    low = src.lower()
    for w in FORBIDDEN_WORDS:
        assert w not in low
