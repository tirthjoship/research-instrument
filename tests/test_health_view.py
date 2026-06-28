# tests/test_health_view.py
import inspect
from types import SimpleNamespace

from adapters.visualization.tabs.stock_analysis import health_view
from domain.fit import FORBIDDEN_WORDS


def _result(**info_over):
    info = {
        "debtToEquity": 12.0,
        "totalCash": 43e9,
        "totalDebt": 9e9,
        "ebitda": 90e9,
        "interestExpense": 1e9,
        "currentRatio": 4.1,
        "quickRatio": 3.5,
    }
    info.update(info_over)
    return SimpleNamespace(info=info, ticker="NVDA")


def test_six_solvency_metrics_and_netcash():
    v = health_view.build_health_view(_result())
    labels = [m.label for m in v["metrics"]]
    assert len(v["metrics"]) == 6
    assert any("Net cash" in lbl for lbl in labels) and any(
        "EBITDA" in lbl for lbl in labels
    )
    nd = next(m for m in v["metrics"] if "EBITDA" in m.label)
    # (9-43)/90 = -0.38 -> net cash, green
    assert nd.tone == "green"


def test_interest_coverage_computed():
    v = health_view.build_health_view(_result())
    ic = next(
        m for m in v["metrics"] if "Int cov" in m.label or "coverage" in m.label.lower()
    )
    assert "90" in ic.value  # 90e9/1e9


def test_fortress_chip_when_net_cash():
    v = health_view.build_health_view(_result())
    assert "FORTRESS" in v["chips"]


def test_panel_renders():
    assert "Health" in health_view.build_health_panel(_result())


def test_no_streamlit_and_clean():
    src = inspect.getsource(health_view)
    assert "import streamlit" not in src
    low = src.lower()
    for w in FORBIDDEN_WORDS:
        assert w not in low
