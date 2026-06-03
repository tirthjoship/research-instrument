"""Tab 2: Model Confidence — Should I trust these predictions?"""

from __future__ import annotations

from typing import Any

import streamlit as st

from adapters.visualization.action_runner import run_backtest
from adapters.visualization.components.charts import (
    ablation_bar_chart,
    accuracy_line_chart,
    shap_bar_chart,
)
from adapters.visualization.components.formatters import status_pill_html
from adapters.visualization.components.metrics import (
    render_inline_context,
    render_verdict_card,
)
from adapters.visualization.components.verdicts import (
    ablation_verdict,
    model_confidence_verdict,
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
    reports = load_backtest_reports(reports_dir)

    if not reports:
        render_verdict_card(
            st,
            "No backtest data available. Run a backtest to evaluate model performance.",
            tone="neutral",
        )
        if st.button("Run Backtest", type="primary", key="run_backtest"):
            progress = st.progress(0)
            status_text = st.empty()

            def update(pct_val: float, msg: str) -> None:
                progress.progress(pct_val)
                status_text.text(msg)

            run_backtest(progress_callback=update)
            st.rerun()
        return

    latest = reports[-1]
    horizons = latest.get("horizons", {})

    horizon_options = list(horizons.keys()) if horizons else ["5d"]
    selected = st.radio("Horizon", horizon_options, horizontal=True)

    if selected and selected in horizons:
        metrics = horizons[selected]
        _render_verdict(metrics)
        _render_accuracy_chart(metrics)

    st.divider()

    st.markdown("#### Ablation Study")
    _render_ablation(reports_dir)

    st.divider()

    st.markdown("#### Feature Importance")
    _render_shap(shap_path)

    st.divider()

    st.markdown("#### Known Limitations")
    st.markdown(
        '<div class="limitation-card">'
        "<ul>"
        "<li>Phase 3A result: technical features alone perform at random on S&P mega-caps</li>"
        "<li>Phase 3B in-sample only — out-of-sample validation pending</li>"
        "<li>101 features wired but only 45 tested in backtest so far</li>"
        "<li>p-value > 0.05 on most horizons — no proven statistical edge yet</li>"
        "</ul>"
        "</div>",
        unsafe_allow_html=True,
    )


def _render_verdict(metrics: dict[str, Any]) -> None:
    """Render model confidence verdict card."""
    p_value = metrics.get("p_value_vs_random", 1.0)
    accuracy = metrics.get("avg_directional_accuracy", 0.0)
    n_folds = metrics.get("n_folds", 0)
    n_preds = metrics.get("n_total_predictions", 0)
    beats_random = p_value < 0.05

    verdict = model_confidence_verdict(accuracy, p_value, n_folds)
    tone = "positive" if beats_random else "negative"

    render_verdict_card(st, verdict, tone=tone)

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


def _render_ablation(reports_dir: str) -> None:
    """Render ablation section with verdict."""
    ablation = load_ablation_results(reports_dir)
    if not ablation:
        render_inline_context(
            st,
            "Run Phase 3B validation to compare technical-only vs combined accuracy.",
        )
        return

    tech_acc = None
    combined_acc = None
    for r in ablation:
        variant = r.get("variant", "")
        acc = r.get("directional_accuracy", 0.0)
        if "technical_only" in variant:
            tech_acc = acc
        elif "sentiment" in variant and "source" not in variant:
            combined_acc = acc

    verdict = ablation_verdict(tech_acc, combined_acc)
    render_inline_context(st, verdict)

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


def _render_shap(shap_path: str) -> None:
    """Render SHAP section with CSS-colored legend."""
    render_inline_context(
        st,
        "Which features drive predictions? Colored by signal layer.",
    )

    st.markdown(
        '<span class="shap-legend-dot" style="background:#2563EB;"></span>Technical '
        '<span class="shap-legend-dot" style="background:#7C3AED;"></span>Sentiment '
        '<span class="shap-legend-dot" style="background:#059669;"></span>Fundamental '
        '<span class="shap-legend-dot" style="background:#EA580C;"></span>Cross-Asset '
        '<span class="shap-legend-dot" style="background:#DC2626;"></span>Event-Causal',
        unsafe_allow_html=True,
    )

    shap_data = load_shap_importance(shap_path)
    if shap_data:
        features = list(shap_data.keys())
        importances = [shap_data[f].get("mean", 0.0) for f in features]
        fig = shap_bar_chart(features, importances)
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.caption("No SHAP data available. Run SHAP analysis to populate.")
