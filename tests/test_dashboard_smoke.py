"""Smoke test — dashboard modules import without Streamlit server."""

from __future__ import annotations


def test_formatters_importable() -> None:
    from adapters.visualization.components.formatters import (
        confidence_bar_html,
        freshness_dot_html,
        freshness_status,
        freshness_status_html,
        grade_badge_html,
        grade_color,
        grade_display_name,
        pct,
        signal_pill_html,
        status_pill_html,
        urgency_badge,
        urgency_pill_html,
    )

    assert callable(grade_color)
    assert callable(grade_display_name)
    assert callable(grade_badge_html)
    assert callable(status_pill_html)
    assert callable(signal_pill_html)
    assert callable(confidence_bar_html)
    assert callable(freshness_status_html)
    assert callable(freshness_dot_html)
    assert callable(urgency_badge)
    assert callable(urgency_pill_html)
    assert callable(pct)
    assert callable(freshness_status)


def test_charts_importable() -> None:
    from adapters.visualization.components.charts import (
        COLOR_PALETTE,
        ablation_bar_chart,
        accuracy_line_chart,
        decay_curve,
        grade_donut,
        sector_heatmap,
        shap_bar_chart,
    )

    assert callable(accuracy_line_chart)
    assert callable(grade_donut)
    assert callable(sector_heatmap)
    assert callable(decay_curve)
    assert callable(shap_bar_chart)
    assert callable(ablation_bar_chart)
    assert isinstance(COLOR_PALETTE, dict)


def test_data_loader_importable() -> None:
    from adapters.visualization.data_loader import (
        load_ablation_results,
        load_backtest_reports,
        load_evaluation_runs,
        load_holdings,
        load_recommendations,
        load_shap_importance,
        load_supply_chains,
        load_watchlist,
    )

    assert callable(load_backtest_reports)
    assert callable(load_recommendations)
    assert callable(load_holdings)
    assert callable(load_watchlist)
    assert callable(load_evaluation_runs)
    assert callable(load_supply_chains)
    assert callable(load_shap_importance)
    assert callable(load_ablation_results)


def test_metrics_importable() -> None:
    from adapters.visualization.components.metrics import (
        render_action_card,
        render_hero_banner,
        render_inline_context,
        render_pick_card,
        render_signal_layer_card,
        render_verdict_card,
    )

    assert callable(render_action_card)
    assert callable(render_signal_layer_card)
    assert callable(render_hero_banner)
    assert callable(render_verdict_card)
    assert callable(render_inline_context)
    assert callable(render_pick_card)


def test_styles_importable() -> None:
    from adapters.visualization.components.styles import GLOBAL_CSS, inject_global_css

    assert callable(inject_global_css)
    assert isinstance(GLOBAL_CSS, str)
    assert "Inter" in GLOBAL_CSS
    assert "#1D4ED8" in GLOBAL_CSS


def test_action_runner_importable() -> None:
    from adapters.visualization.action_runner import (
        run_add_holding,
        run_add_watchlist,
        run_backtest,
        run_full_cycle,
        run_monitor_holdings,
        run_tournament,
    )

    assert callable(run_monitor_holdings)
    assert callable(run_add_holding)
    assert callable(run_add_watchlist)
    assert callable(run_full_cycle)
    assert callable(run_tournament)
    assert callable(run_backtest)


def test_verdicts_importable() -> None:
    from adapters.visualization.components.verdicts import (
        ablation_verdict,
        command_center_verdict,
        model_confidence_verdict,
        pick_verdict,
        signal_layer_verdict,
    )

    assert callable(command_center_verdict)
    assert callable(model_confidence_verdict)
    assert callable(signal_layer_verdict)
    assert callable(pick_verdict)
    assert callable(ablation_verdict)
