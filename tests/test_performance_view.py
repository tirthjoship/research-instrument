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


def test_price_history_fills_long_return_drawdown_and_viz() -> None:
    # ~3y of mostly-rising closes with a dip (for drawdown) + steadier SPY
    closes = [100 * (1.0009**i) for i in range(800)]
    closes[600:640] = [c * 0.7 for c in closes[600:640]]  # a drawdown
    spy = [400 * (1.0004**i) for i in range(800)]
    result = SimpleNamespace(
        info={"52WeekChange": 0.42, "SandP52WeekChange": 0.14, "beta": 1.7},
        current_price=closes[-1],
        ticker="NVDA",
        price_history={"closes": closes, "spy_closes": spy},
    )
    v = performance_view.build_performance_view(result)
    long_m = next(m for m in v["metrics"] if m.key in ("ret_long", "ret_3y"))
    assert long_m.value != "—" and "3Y return" in long_m.label  # 800 days -> 3Y
    mdd = next(m for m in v["metrics"] if m.key == "max_drawdown")
    assert mdd.value != "—" and mdd.value.startswith("-")
    html = performance_view.build_performance_panel(result)
    assert "by horizon" in html and "Relative strength" in html
    assert "returns-by-horizon — data gap" not in html


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


def test_beta_formatted_without_multiplier_sign() -> None:
    v = performance_view.build_performance_view(_result())
    beta = next(m for m in v["metrics"] if m.label == "Beta")
    assert beta.value == "1.7"  # one decimal, no '×'


def test_returns_by_horizon_show_benchmark() -> None:
    closes = [100 * (1.0009**i) for i in range(800)]
    spy = [400 * (1.0004**i) for i in range(800)]
    result = SimpleNamespace(
        info={"52WeekChange": 0.42, "SandP52WeekChange": 0.14, "beta": 1.7},
        current_price=closes[-1],
        ticker="NVDA",
        price_history={"closes": closes, "spy_closes": spy},
    )
    html = performance_view.build_performance_panel(result)
    # one "S&P" is the relative-strength subhead; the per-horizon benchmark bars
    # add several more (one label per horizon).
    assert html.count("S&P") >= 3


def test_panel_renders() -> None:
    assert "Performance" in performance_view.build_performance_panel(_result())


def test_no_streamlit_and_clean() -> None:
    src = inspect.getsource(performance_view)
    assert "import streamlit" not in src
    low = src.lower()
    for w in FORBIDDEN_WORDS:
        assert w not in low
