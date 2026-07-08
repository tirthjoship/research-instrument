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


def test_dispersion_sub_shows_wide_when_spread_large():
    v = analyst_view.build_analyst_view(_result())
    disp = next(m for m in v["metrics"] if "ispersion" in m.label)
    assert disp.value == "$110"
    assert disp.sub == "wide"


def test_reframe_summary_includes_target_range():
    v = analyst_view.build_analyst_view(_result())
    html = v["reframe_html"] or ""
    assert "$150" in html and "$260" in html
    assert "real disagreement" in html


def test_claim_headline_mockup_style():
    v = analyst_view.build_analyst_view(_result())
    assert "Street leans positive" in v["claim"]
    assert "their view, not ours" in v["claim"]


def test_rating_distribution_uses_tier_labels_not_numbers():
    result = SimpleNamespace(
        analyst_panel=_panel(),
        ticker="NVDA",
        rating_distribution={"r1": 28, "r2": 16, "r3": 7, "r4": 1, "r5": 0},
    )
    html = analyst_view.build_analyst_panel(result)
    assert "Str. pos." in html
    assert "Positive" in html
    assert "Skewed positive" in html
    assert ">1<" not in html.split("Rating distribution")[1][:400]


def test_targets_chip_shows_arrow_not_dollar_amount():
    v = analyst_view.build_analyst_view(_result())
    assert "TARGETS" in v["chips"]
    assert "$200" not in v["chips"]


def test_wide_dispersion_verdict_shows_target_range():
    v = analyst_view.build_analyst_view(_result())
    assert any(
        vv.tone == "cau" and "$150" in vv.text and "$260" in vv.text
        for vv in v["verdicts"]
    )


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
    up = next(m for m in v["metrics"] if "move" in m.label.lower())
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


def test_price_vs_target_chart_renders_when_price_history_available():
    # price_history is already fetched for the Performance panel — the Analyst
    # panel's "mean-target trend" slot should use it instead of a dead data-gap.
    closes = [150.0 + i * 0.2 for i in range(60)]
    result = SimpleNamespace(
        analyst_panel=_panel(), ticker="NVDA", price_history={"closes": closes}
    )
    html = analyst_view.build_analyst_panel(result)
    assert "mean-target trend not wired" not in html
    assert "Price vs. mean target" in html
    assert "polyline" in html
    chart_region = html.split("Price vs. mean target")[1].split("sa-verdrow")[0]
    assert "revision history" in chart_region
    # price and target lines converge (both end near $200) — inline SVG labels
    # would overlap into garbled text, so this chart must not emit any.
    assert "<text" not in chart_region
    assert "$200" in chart_region


def test_price_vs_target_chart_datagap_without_price_history():
    result = SimpleNamespace(analyst_panel=_panel(), ticker="NVDA")
    html = analyst_view.build_analyst_panel(result)
    assert "data gap" in html.split("Price vs. mean target")[1][:200]


def test_verdict_uses_analyst_context_not_chart_meta():
    no_history = SimpleNamespace(analyst_panel=_panel(), ticker="NVDA")
    v_gap = analyst_view.build_analyst_view(no_history)
    assert any("third-party context" in vv.text for vv in v_gap["verdicts"])
    assert not any("price vs" in vv.text.lower() for vv in v_gap["verdicts"])

    closes = [150.0 + i * 0.2 for i in range(60)]
    with_history = SimpleNamespace(
        analyst_panel=_panel(), ticker="NVDA", price_history={"closes": closes}
    )
    v_have = analyst_view.build_analyst_view(with_history)
    assert any("third-party context" in vv.text for vv in v_have["verdicts"])


def test_no_streamlit_and_clean():
    src = inspect.getsource(analyst_view)
    assert "import streamlit" not in src
    low = src.lower()
    for w in FORBIDDEN_WORDS:
        assert w not in low
