"""Smoke test — dashboard module imports without Streamlit server."""

from __future__ import annotations


def test_formatters_importable() -> None:
    from adapters.visualization.components.formatters import (
        direction_icon,
        freshness_status,
        grade_color,
        pct,
        urgency_badge,
    )

    assert callable(grade_color)
    assert callable(direction_icon)
    assert callable(urgency_badge)
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
        render_metric,
        render_signal_layer_card,
    )

    assert callable(render_metric)
    assert callable(render_action_card)
    assert callable(render_signal_layer_card)
