"""Tests for adapters/visualization/components/cards.py — TDD first."""

from __future__ import annotations

from adapters.visualization.components.cards import (
    criteria_card,
    loading_stepper_html,
    metric_kpi,
    mini_sparkline,
    price_range_bar,
    verdict_bullet,
)

# ---------------------------------------------------------------------------
# criteria_card
# ---------------------------------------------------------------------------


def test_criteria_card_dot_counts_4_of_6() -> None:
    html = criteria_card("Valuation Score", 4, 6, "Moderate valuation")
    # 4 filled dots (&#9679;) and 2 empty dots (&#9675;)
    assert html.count("&#9679;") == 4
    assert html.count("&#9675;") == 2


def test_criteria_card_dot_counts_0_of_5() -> None:
    html = criteria_card("Risk Score", 0, 5, "Very high risk")
    assert html.count("&#9679;") == 0
    assert html.count("&#9675;") == 5


def test_criteria_card_contains_title_and_summary() -> None:
    html = criteria_card("Momentum", 3, 5, "Trending upward")
    assert "Momentum" in html
    assert "Trending upward" in html


def test_criteria_card_uses_ws_card_class() -> None:
    html = criteria_card("Test", 2, 4, "Summary")
    assert "ws-card" in html


def test_criteria_card_green_filled_dot_color() -> None:
    html = criteria_card("Test", 1, 3, "Summary")
    assert "#16A34A" in html


# ---------------------------------------------------------------------------
# verdict_bullet
# ---------------------------------------------------------------------------


def test_verdict_bullet_pass_has_checkmark() -> None:
    html = verdict_bullet("pass", "P/E below median")
    assert "&#10003;" in html
    assert "#16A34A" in html


def test_verdict_bullet_fail_has_x() -> None:
    html = verdict_bullet("fail", "Debt ratio too high")
    assert "&#10007;" in html
    assert "#DC2626" in html


def test_verdict_bullet_warn_has_warning() -> None:
    html = verdict_bullet("warn", "Moderate debt")
    assert "&#9888;" in html
    assert "#F59E0B" in html


def test_verdict_bullet_contains_text() -> None:
    html = verdict_bullet("pass", "Revenue growing fast")
    assert "Revenue growing fast" in html


# ---------------------------------------------------------------------------
# metric_kpi
# ---------------------------------------------------------------------------


def test_metric_kpi_renders_value_and_label() -> None:
    html = metric_kpi("P/E Ratio", "18.5x")
    assert "18.5x" in html
    assert "P/E Ratio" in html


def test_metric_kpi_renders_context() -> None:
    html = metric_kpi("Revenue", "$42B", context="vs $38B last year")
    assert "vs $38B last year" in html


def test_metric_kpi_custom_color() -> None:
    html = metric_kpi("Price", "$150", color="#16A34A")
    assert "#16A34A" in html


# ---------------------------------------------------------------------------
# price_range_bar
# ---------------------------------------------------------------------------


def test_price_range_bar_includes_prices() -> None:
    html = price_range_bar(current=155.0, low=140.0, high=180.0)
    assert "140" in html
    assert "180" in html
    assert "155" in html


def test_price_range_bar_includes_target() -> None:
    html = price_range_bar(current=155.0, low=140.0, high=180.0, target=170.0)
    assert "170" in html


def test_price_range_bar_no_target() -> None:
    html = price_range_bar(current=155.0, low=140.0, high=180.0)
    # Should render without error, no target label
    assert "155" in html


# ---------------------------------------------------------------------------
# mini_sparkline
# ---------------------------------------------------------------------------


def test_mini_sparkline_returns_svg_for_valid_data() -> None:
    html = mini_sparkline([100.0, 102.0, 101.5, 104.0])
    assert "<svg" in html
    assert "polyline" in html


def test_mini_sparkline_returns_dash_for_empty() -> None:
    html = mini_sparkline([])
    assert html == "\u2014"


def test_mini_sparkline_returns_dash_for_single_element() -> None:
    html = mini_sparkline([100.0])
    assert html == "\u2014"


def test_mini_sparkline_green_when_up() -> None:
    html = mini_sparkline([100.0, 110.0])
    assert "#16A34A" in html


def test_mini_sparkline_red_when_down() -> None:
    html = mini_sparkline([110.0, 100.0])
    assert "#DC2626" in html


# ---------------------------------------------------------------------------
# loading_stepper_html
# ---------------------------------------------------------------------------


def test_loading_stepper_renders_all_steps() -> None:
    steps = ["Fetch data", "Score signals", "Rank picks"]
    html = loading_stepper_html(steps, current=1)
    for step in steps:
        assert step in html


def test_loading_stepper_completed_step_has_checkmark() -> None:
    steps = ["Step A", "Step B", "Step C"]
    html = loading_stepper_html(steps, current=2)
    # Steps 0 and 1 are completed
    assert "&#10003;" in html


def test_loading_stepper_current_step_has_blue_dot() -> None:
    steps = ["Step A", "Step B", "Step C"]
    html = loading_stepper_html(steps, current=1)
    assert "#2563EB" in html


def test_loading_stepper_progress_percentage() -> None:
    steps = ["A", "B", "C", "D"]
    html = loading_stepper_html(steps, current=1)
    # (1 + 1) / 4 * 100 = 50%
    assert "50" in html
