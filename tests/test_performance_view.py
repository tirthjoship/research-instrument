"""Tests for performance_view (spec D11): 6 price/return metrics, no margins/ROE."""

import inspect
from types import SimpleNamespace

from adapters.visualization.tabs.stock_analysis import performance_view
from domain.fit import FORBIDDEN_WORDS


def _result(**info_over):  # type: ignore[no-untyped-def]
    info = {
        "52WeekChange": 0.42,
        "SandP52WeekChange": 0.14,
        "beta": 1.7,
        "twoHundredDayAverage": 130.0,
        "fiftyDayAverage": 160.0,
    }
    info.update(info_over)
    return SimpleNamespace(info=info, current_price=172.0, ticker="NVDA")


def test_six_metrics_and_excess() -> None:
    v = performance_view.build_performance_view(_result())
    assert len(v["metrics"]) == 6
    ex = next(m for m in v["metrics"] if "vs S&P" in m.label)
    assert "+28" in ex.value or "28" in ex.value  # 42-14 = 28 pts


def test_no_margins_or_roe_present() -> None:
    v = performance_view.build_performance_view(_result())
    labels = " ".join(m.label.lower() for m in v["metrics"])
    assert "margin" not in labels and "roe" not in labels  # moved to Profitability


def test_threeyear_and_drawdown_are_datagap() -> None:
    v = performance_view.build_performance_view(_result())
    ty = next(m for m in v["metrics"] if "3Y" in m.label)
    dd = next(m for m in v["metrics"] if "drawdown" in m.label.lower())
    assert ty.value == "—" and dd.value == "—"


def test_high_beta_amber() -> None:
    v = performance_view.build_performance_view(_result())
    assert "HIGH-BETA" in v["chips"]


def test_panel_renders() -> None:
    assert "Performance" in performance_view.build_performance_panel(_result())


def test_no_streamlit_and_clean() -> None:
    src = inspect.getsource(performance_view)
    assert "import streamlit" not in src
    low = src.lower()
    for w in FORBIDDEN_WORDS:
        assert w not in low
