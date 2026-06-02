"""Tab 2: Model Confidence — Should I trust these predictions?"""

from __future__ import annotations

from typing import Any

import streamlit as st

from adapters.visualization.components.charts import (
    ablation_bar_chart,
    accuracy_line_chart,
    shap_bar_chart,
)
from adapters.visualization.data_loader import (
    load_ablation_results,
    load_backtest_reports,
    load_shap_importance,
)

REPORTS_DIR = "data/reports"
SHAP_PATH = "data/reports/shap_importance.json"


def render(reports_dir: str = REPORTS_DIR, shap_path: str = SHAP_PATH) -> None:
    """Render the Model Confidence tab."""
    st.header("Model Confidence")

    reports = load_backtest_reports(reports_dir)

    if not reports:
        st.warning(
            "No backtest reports found. Run:\n\n"
            "```\npython -m application.cli backtest --market us\n```"
        )
        return

    latest = reports[-1]
    horizons = latest.get("horizons", {})

    # Horizon selector
    horizon_options = list(horizons.keys()) if horizons else ["5d"]
    selected = st.radio("Horizon", horizon_options, horizontal=True)

    if selected and selected in horizons:
        metrics = horizons[selected]
        _render_headline(metrics)
        _render_accuracy_chart(metrics)
    else:
        st.info("Select a horizon to view metrics.")

    st.divider()

    # Ablation study
    st.subheader("Ablation Study")
    ablation = load_ablation_results(reports_dir)
    if ablation:
        variants = [r.get("variant", "?") for r in ablation]
        accs = [r.get("directional_accuracy", 0.0) for r in ablation]
        fig = ablation_bar_chart(variants, accs)
        st.plotly_chart(fig, use_container_width=True)

        for r in ablation:
            pval = r.get("p_value", 1.0)
            sig = "✅ Significant" if float(str(pval)) < 0.05 else "❌ Not significant"
            st.caption(f"{r.get('variant', '?')}: p={pval:.4f} ({sig})")
    else:
        st.info("Run Phase 3B validation for ablation data.")

    st.divider()

    # SHAP feature importance
    st.subheader("SHAP Feature Importance")
    shap_data = load_shap_importance(shap_path)
    if shap_data:
        features = list(shap_data.keys())
        importances = [shap_data[f].get("mean", 0.0) for f in features]
        fig = shap_bar_chart(features, importances)
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("Run SHAP analysis for feature importance data.")

    st.divider()

    # Honest limitations
    st.subheader("Known Limitations")
    st.warning(
        "- Phase 3A result: technical features alone ≈ random on S&P mega-caps\n"
        "- Phase 3B in-sample only — out-of-sample validation pending\n"
        "- 101 features wired but only 45 tested in backtest so far\n"
        "- p-value > 0.05 on most horizons — no proven statistical edge yet"
    )


def _render_headline(metrics: dict[str, Any]) -> None:
    """Big headline: does model beat random?"""
    p_value = metrics.get("p_value_vs_random", 1.0)
    accuracy = metrics.get("avg_directional_accuracy", 0.0)
    n_folds = metrics.get("n_folds", 0)
    n_preds = metrics.get("n_total_predictions", 0)

    beats_random = p_value < 0.05

    cols = st.columns(4)
    cols[0].metric(
        "Beats Random?",
        "Yes ✅" if beats_random else "No ❌",
        delta=f"p={p_value:.4f}",
    )
    cols[1].metric("Avg Accuracy", f"{accuracy:.1%}")
    cols[2].metric("Folds", str(n_folds))
    cols[3].metric("Predictions", str(n_preds))


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
