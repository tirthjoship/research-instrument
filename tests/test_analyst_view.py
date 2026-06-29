# tests/test_analyst_view.py (contract)
import inspect
from types import SimpleNamespace

from adapters.visualization.tabs.stock_analysis import analyst_view
from domain.fit import FORBIDDEN_WORDS


def _panel(gap=False):
    return SimpleNamespace(
        count=0 if gap else 42,
        mean_rating=1.6,
        target_mean=200.0,
        target_high=260.0,
        target_low=150.0,
        as_of="2026-06-27",
        data_gap=gap,
    )


def _result(gap=False):
    return SimpleNamespace(analyst_panel=_panel(gap), ticker="NVDA")


def test_six_metrics_consensus_dispersion():
    v = analyst_view.build_analyst_view(_result())
    assert len(v["metrics"]) == 6
    assert any("Consensus" in m.label or "onsensus" in m.label for m in v["metrics"])
    assert any("ispersion" in m.label for m in v["metrics"])


def test_chips_petrol_never_green():
    v = analyst_view.build_analyst_view(_result())
    assert "t-petrol" in v["chips"]
    assert "t-green" not in v["chips"]


def test_distribution_and_target90d_datagap():
    v = analyst_view.build_analyst_view(_result())
    assert any(m.value == "—" for m in v["metrics"])


def test_upside_tile_from_target_and_price():
    result = SimpleNamespace(
        analyst_panel=_panel(), ticker="NVDA", current_price=172.0, info={}
    )
    v = analyst_view.build_analyst_view(result)
    up = next(m for m in v["metrics"] if "Upside" in m.label)
    assert up.value == "+16%"  # (200-172)/172
    assert up.tone == "petrol"  # Street-derived, never green


def test_fwd_eps_tile_from_info():
    result = SimpleNamespace(
        analyst_panel=_panel(),
        ticker="NVDA",
        current_price=172.0,
        info={"forwardEps": 4.5},
    )
    v = analyst_view.build_analyst_view(result)
    eps = next(m for m in v["metrics"] if "EPS" in m.label)
    assert eps.value == "$4.50" and eps.tone == "petrol"


def test_datagap_panel_degrades():
    html = analyst_view.build_analyst_panel(_result(gap=True))
    assert "Analyst" in html


def test_panel_renders():
    assert "Analyst" in analyst_view.build_analyst_panel(_result())


def test_no_streamlit_and_clean():
    src = inspect.getsource(analyst_view)
    assert "import streamlit" not in src
    low = src.lower()
    for w in FORBIDDEN_WORDS:
        assert w not in low
