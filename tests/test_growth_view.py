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


def _df6() -> pd.DataFrame:
    cols = [
        "2025-03-31",
        "2024-12-31",
        "2024-09-30",
        "2024-06-30",
        "2024-03-31",
        "2023-12-31",
    ]
    revs = [26e9, 22e9, 20e9, 18e9, 16e9, 14e9]  # newest-first
    return pd.DataFrame(
        {c: {"Total Revenue": r, "Net Income": r * 0.5} for c, r in zip(cols, revs)}
    )


def _qcf6() -> pd.DataFrame:
    cols = [
        "2025-03-31",
        "2024-12-31",
        "2024-09-30",
        "2024-06-30",
        "2024-03-31",
        "2023-12-31",
    ]
    fcfs = [12e9, 11e9, 10e9, 9e9, 8e9, 7e9]
    return pd.DataFrame({c: {"Free Cash Flow": f} for c, f in zip(cols, fcfs)})


def test_fcf_yoy_peer_rank_and_trajectory_wired() -> None:
    result = SimpleNamespace(
        info={"revenueGrowth": 0.69, "earningsGrowth": 0.82},
        quarterly_financials=_df6(),
        quarterly_cashflow=_qcf6(),
        peer_data=[
            {"ticker": "AMD", "revenue_growth": 0.30},
            {"ticker": "QCOM", "revenue_growth": 0.10},
        ],
        ticker="NVDA",
    )
    v = growth_view.build_growth_view(result)
    fcf = next(m for m in v["metrics"] if "FCF YoY" in m.label)
    assert fcf.value == "+50%" and fcf.tone == "green"  # 12B vs 8B a year ago
    rank = next(m for m in v["metrics"] if "Peer rank" in m.label)
    assert rank.value == "100th"  # 0.69 beats both peers
    assert len(v["yoy_traj"]) == 2  # 6 quarters -> 2 YoY points
    html = growth_view.build_growth_panel(result)
    assert "YoY growth trajectory" in html
    assert "needs &gt;=5 quarters" not in html  # real graph, not the gap caption


def test_3y_cagr_and_fwd_rev_wired() -> None:
    result = SimpleNamespace(
        info={"revenueGrowth": 0.69},
        quarterly_financials=_df6(),
        annual_revenue=[27e9, 60e9, 130e9, 200e9],  # ~3y span
        forward_revenue_growth=0.48,
        ticker="NVDA",
    )
    v = growth_view.build_growth_view(result)
    cagr = next(m for m in v["metrics"] if "CAGR" in m.label)
    assert cagr.value not in ("—", "") and cagr.value.startswith("+")
    fwd = next(m for m in v["metrics"] if "Fwd rev" in m.label)
    assert fwd.value == "+48%"


def _result_annual(annual: list[float]) -> SimpleNamespace:
    return SimpleNamespace(
        info={"revenueGrowth": 0.69, "earningsGrowth": 0.82},
        quarterly_financials=_df6(),
        annual_revenue=annual,
        ticker="NVDA",
    )


def test_declining_trajectory_is_amber_and_decelerating() -> None:
    # YoY rate falls 200% -> 100% -> 50%: growth still positive but decelerating
    result = _result_annual([10e9, 30e9, 60e9, 90e9])
    v = growth_view.build_growth_view(result)
    assert v["traj_dir"] == "down"
    assert "DECELERATING" in v["chips"] and "t-amber" in v["chips"]
    html = growth_view.build_growth_panel(result)
    assert "#b45309" in html  # amber trajectory line, not green
    assert "decelerating" in html.lower()


def test_rising_trajectory_is_green_and_accelerating() -> None:
    # YoY rate rises 10% -> 20% -> ~30%: accelerating
    result = _result_annual([100e9, 110e9, 132e9, 172e9])
    v = growth_view.build_growth_view(result)
    assert v["traj_dir"] == "up"
    assert "ACCELERATING" in v["chips"] and "t-green" in v["chips"]
    html = growth_view.build_growth_panel(result)
    assert "#2f9e44" in html  # green trajectory line
    assert "accelerating" in html.lower()


def test_panel_renders() -> None:
    html = growth_view.build_growth_panel(_result())
    assert "sa-pnl" in html and "Growth" in html and "sa-drill" not in html


def test_no_streamlit_and_clean() -> None:
    src = inspect.getsource(growth_view)
    assert "import streamlit" not in src
    low = src.lower()
    for w in FORBIDDEN_WORDS:
        assert w not in low
