# tests/test_health_view.py
import inspect
from types import SimpleNamespace

import pandas as pd

from adapters.visualization.tabs.stock_analysis import health_view
from domain.fit import FORBIDDEN_WORDS


def _result(qbs=None, ticker="NVDA", **info_over):
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
    return SimpleNamespace(info=info, ticker=ticker, quarterly_balance_sheet=qbs)


def _qbs(cash_newest_first, debt_newest_first):
    cols = [f"2025-{m:02d}-01" for m in range(len(cash_newest_first), 0, -1)]
    return pd.DataFrame(
        {
            c: {"Cash And Cash Equivalents": ca, "Total Debt": d}
            for c, ca, d in zip(cols, cash_newest_first, debt_newest_first)
        }
    )


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


def test_ratios_formatted_cleanly():
    v = health_view.build_health_view(
        _result(debtToEquity=6.555, currentRatio=3.441, quickRatio=2.139)
    )
    by = {m.label: m.value for m in v["metrics"]}
    assert by["D/E ratio"] == "7%"  # integer percent, not 6.555%
    assert by["Current ratio"] == "3.4×"  # one decimal, not 3.441×
    assert by["Quick ratio"] == "2.1×"
    nd = next(m for m in v["metrics"] if "EBITDA" in m.label)
    assert nd.value == "-0.4×"  # one decimal, not -0.38×


def test_coverage_falls_back_to_cash_debt_when_no_interest():
    v = health_view.build_health_view(_result(interestExpense=None))
    cov = v["metrics"][4]
    assert cov.label == "Cash/Debt" and cov.value == "4.8×"  # 43/9


def test_trend_verdict_describes_trend_when_bs_available():
    qbs = _qbs([43e9, 40e9, 36e9, 30e9], [9e9, 9e9, 10e9, 11e9])  # cash rising
    v = health_view.build_health_view(_result(qbs=qbs))
    joined = " ".join(vd.text for vd in v["verdicts"]).lower()
    assert "not wired" not in joined and "trend" in joined
    assert "not wired" not in v["reframe"].lower()


def test_trend_datagap_verdict_when_no_bs():
    v = health_view.build_health_view(_result(qbs=None))
    joined = " ".join(vd.text for vd in v["verdicts"]).lower()
    assert "not wired" in joined or "data gap" in joined


def test_fortress_chip_when_net_cash():
    v = health_view.build_health_view(_result())
    assert "FORTRESS" in v["chips"]


def test_panel_renders():
    assert "Health" in health_view.build_health_panel(_result())


def test_canadian_ticker_net_cash_shows_cad_symbol():
    """A TSX-suffixed ticker's Net cash tile must show C$, not bare $ — showing
    bare $ would misrepresent CAD amounts as USD."""
    v = health_view.build_health_view(_result(ticker="RY.TO"))
    net_cash = next(m for m in v["metrics"] if "Net cash" in m.label)
    assert "C$" in net_cash.value
    assert "$" not in net_cash.value.replace("C$", "")


def test_no_streamlit_and_clean():
    src = inspect.getsource(health_view)
    assert "import streamlit" not in src
    low = src.lower()
    for w in FORBIDDEN_WORDS:
        assert w not in low
