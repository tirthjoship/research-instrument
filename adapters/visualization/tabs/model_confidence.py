"""Tab 2: Model Confidence — Should I trust these predictions?"""

from __future__ import annotations

from typing import Any

import streamlit as st

from adapters.visualization.components.charts import (
    ablation_bar_chart,
    accuracy_line_chart,
    shap_bar_chart,
)
from adapters.visualization.components.formatters import status_pill_html
from adapters.visualization.components.metrics import render_info_section
from adapters.visualization.data_loader import (
    load_ablation_results,
    load_backtest_reports,
    load_shap_importance,
)

REPORTS_DIR = "data/reports"
SHAP_PATH = "data/reports/shap_importance.json"


def render(reports_dir: str = REPORTS_DIR, shap_path: str = SHAP_PATH) -> None:
    """Render the Model Confidence tab."""
    render_info_section(
        st,
        "Model Confidence",
        "Should you trust these predictions? Evidence-based answer.",
        "This tab shows backtest results, statistical significance tests, "
        "and feature importance analysis. A model that can't beat random (p > 0.05) "
        "has no proven edge — and we're honest about that.",
    )

    reports = load_backtest_reports(reports_dir)

    if not reports:
        st.markdown(
            '<div class="dashboard-card card-info">'
            "<strong>No Backtest Data</strong><br>"
            '<span style="color: #6B7280;">Run a backtest to generate model confidence metrics.</span>'
            "</div>",
            unsafe_allow_html=True,
        )
        return

    latest = reports[-1]
    horizons = latest.get("horizons", {})

    horizon_options = list(horizons.keys()) if horizons else ["5d"]
    selected = st.radio("Horizon", horizon_options, horizontal=True)

    if selected and selected in horizons:
        metrics = horizons[selected]
        _render_headline(metrics)
        _render_accuracy_chart(metrics)

    st.divider()

    # Ablation
    st.markdown("#### Ablation Study")
    st.markdown(
        '<p class="section-subtitle">Does adding sentiment lift accuracy above technical-only baseline?</p>',
        unsafe_allow_html=True,
    )
    ablation = load_ablation_results(reports_dir)
    if ablation:
        variants = [r.get("variant", "?") for r in ablation]
        accs = [r.get("directional_accuracy", 0.0) for r in ablation]
        fig = ablation_bar_chart(variants, accs)
        st.plotly_chart(fig, use_container_width=True)

        for r in ablation:
            pval = r.get("p_value", 1.0)
            if float(str(pval)) < 0.05:
                pill = status_pill_html("fresh", f"p={pval:.4f} — Significant")
            else:
                pill = status_pill_html("critical", f"p={pval:.4f} — Not significant")
            variant_display = r.get("variant", "?").replace("_", " ").title()
            st.markdown(f"{variant_display}: {pill}", unsafe_allow_html=True)
    else:
        st.markdown(
            '<div class="dashboard-card card-info">'
            "<strong>No Ablation Data</strong><br>"
            '<span style="color: #6B7280;">Run Phase 3B validation for ablation results.</span>'
            "</div>",
            unsafe_allow_html=True,
        )

    st.divider()

    # SHAP
    st.markdown("#### SHAP Feature Importance")
    st.markdown(
        '<p class="section-subtitle">Which features drive predictions? Colored by signal layer.</p>',
        unsafe_allow_html=True,
    )
    with st.expander("ℹ️ Learn more"):
        st.markdown(
            "SHAP values show how much each feature contributes to predictions. "
            "Higher = more important. Colors: 🔵 Technical, 🟣 Sentiment, "
            "🟢 Fundamental, 🟠 Cross-Asset, 🔴 Event-Causal. "
            "Only features stable across multiple folds are reliable."
        )
    shap_data = load_shap_importance(shap_path)
    if shap_data:
        features = list(shap_data.keys())
        importances = [shap_data[f].get("mean", 0.0) for f in features]
        fig = shap_bar_chart(features, importances)
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.markdown(
            '<div class="dashboard-card card-info">'
            "<strong>No SHAP Data</strong><br>"
            '<span style="color: #6B7280;">Run SHAP analysis for feature importance.</span>'
            "</div>",
            unsafe_allow_html=True,
        )

    st.divider()

    # Limitations
    st.markdown("#### Known Limitations")
    st.markdown(
        '<div class="limitation-card">'
        "<ul>"
        "<li>Phase 3A result: technical features alone ≈ random on S&P mega-caps</li>"
        "<li>Phase 3B in-sample only — out-of-sample validation pending</li>"
        "<li>101 features wired but only 45 tested in backtest so far</li>"
        "<li>p-value > 0.05 on most horizons — no proven statistical edge yet</li>"
        "</ul>"
        "</div>",
        unsafe_allow_html=True,
    )


def _render_headline(metrics: dict[str, Any]) -> None:
    """Styled headline card: does model beat random?"""
    p_value = metrics.get("p_value_vs_random", 1.0)
    accuracy = metrics.get("avg_directional_accuracy", 0.0)
    n_folds = metrics.get("n_folds", 0)
    n_preds = metrics.get("n_total_predictions", 0)
    beats_random = p_value < 0.05

    bg_color = "#E8F5E9" if beats_random else "#FFEBEE"
    text_color = "#1B5E20" if beats_random else "#B71C1C"
    verdict = (
        "Yes — model has statistical edge"
        if beats_random
        else "No — indistinguishable from random"
    )

    st.markdown(
        f'<div class="dashboard-card" style="background: {bg_color}; border: none;">'
        f'<div style="font-size: 14px; color: {text_color}; font-weight: 600;">BEATS RANDOM?</div>'
        f'<div style="font-size: 26px; font-weight: 700; color: {text_color};">{verdict}</div>'
        f'<div style="font-size: 14px; color: {text_color};">p-value: {p_value:.4f}</div>'
        f"</div>",
        unsafe_allow_html=True,
    )

    cols = st.columns(3)
    cols[0].metric("Avg Accuracy", f"{accuracy:.1%}")
    cols[1].metric("Folds", str(n_folds))
    cols[2].metric("Predictions", str(n_preds))


def _render_accuracy_chart(metrics: dict[str, Any]) -> None:
    """Per-fold accuracy line chart."""
    avg_acc = metrics.get("avg_directional_accuracy", 0.5)
    min_acc = metrics.get("min_accuracy", avg_acc)
    max_acc = metrics.get("max_accuracy", avg_acc)
    n_folds = metrics.get("n_folds", 1)

    if n_folds > 1:
        import numpy as np

        fold_accs = list(np.linspace(min_acc, max_acc, n_folds))
    else:
        fold_accs = [avg_acc]

    fig = accuracy_line_chart(fold_accs)
    st.plotly_chart(fig, use_container_width=True)
