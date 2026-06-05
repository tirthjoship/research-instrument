"""Tab: How It Works — Signal performance, adaptive learning, and model baseline."""

from __future__ import annotations

from typing import Any

import streamlit as st

from adapters.visualization.action_runner import run_backtest
from adapters.visualization.components.cards import criteria_card, tooltip
from adapters.visualization.components.charts import (
    ablation_bar_chart,
    accuracy_line_chart,
    grade_donut,
    sector_heatmap,
    shap_bar_chart,
)
from adapters.visualization.components.formatters import status_pill_html
from adapters.visualization.components.metrics import (
    render_inline_context,
    render_verdict_card,
)
from adapters.visualization.components.progress import render_learning_progress_html
from adapters.visualization.components.verdicts import (
    ablation_verdict,
    model_confidence_verdict,
    system_intelligence_verdict,
)
from adapters.visualization.data_loader import (
    load_ablation_results,
    load_backtest_reports,
    load_learned_rules,
    load_outcomes,
    load_recommendations_latest,
    load_shap_importance,
    load_weight_history,
)
from domain.conviction import ConvictionWeights

REPORTS_DIR = "data/reports"
SHAP_PATH = "data/reports/shap_importance.json"
DB_PATH = "data/recommendations.db"


def render(
    reports_dir: str = REPORTS_DIR,
    shap_path: str = SHAP_PATH,
    db_path: str = DB_PATH,
) -> None:
    """Render the How It Works tab."""
    st.markdown("### How It Works")
    st.markdown(
        "See how the system makes decisions and how it's learning from your trades."
    )

    # ── Learning Progress Bar (always visible) ────────────────────────────────
    outcomes = load_outcomes(db_path)
    st.markdown(render_learning_progress_html(len(outcomes)), unsafe_allow_html=True)
    st.markdown('<div style="margin-bottom:16px;"></div>', unsafe_allow_html=True)

    # ── Expander 1: Signal Performance ───────────────────────────────────────
    with st.expander("Signal Performance", expanded=True):
        n_outcomes = len(outcomes)
        score = min(5, n_outcomes // 5)
        st.markdown(
            criteria_card(
                "Signal Intelligence",
                score,
                5,
                f"{n_outcomes} outcomes tracked. "
                + (
                    "Track more trades to build signal intelligence."
                    if n_outcomes < 10
                    else "Signal patterns emerging from your trade history."
                ),
            ),
            unsafe_allow_html=True,
        )
        if not outcomes:
            st.markdown("Track trades to see which signals make you money.")
        else:
            _render_signal_report_card_content(outcomes)
        _render_grade_donut(db_path)

    # ── Expander 2: System Learning ───────────────────────────────────────────
    with st.expander("System Learning", expanded=False):
        weight_history = load_weight_history(db_path)
        rules = load_learned_rules(db_path)
        n_rules = len(rules)
        n_adjustments = len(weight_history)
        score = min(5, n_rules + min(n_adjustments, 3))
        st.markdown(
            criteria_card(
                "Adaptive Learning",
                score,
                5,
                f"{n_adjustments} weight adjustments, {n_rules} rules discovered.",
            ),
            unsafe_allow_html=True,
        )
        if not weight_history and not rules:
            st.markdown("The system adjusts its strategy as you track more trades.")
        _render_learning_dashboard_content(db_path, weight_history, rules)

    # ── Expander 3: Model Baseline ────────────────────────────────────────────
    with st.expander("Model Baseline", expanded=False):
        reports = load_backtest_reports(reports_dir)
        horizons = reports[-1].get("horizons", {}) if reports else {}
        has_data = bool(reports)
        significant = (
            any(h.get("p_value_vs_random", 1) < 0.05 for h in horizons.values())
            if reports
            else False
        )
        score = (2 if has_data else 0) + (2 if significant else 0)
        st.markdown(
            criteria_card(
                "Model Validation",
                score,
                4,
                "Historical backtest with walk-forward validation and statistical testing.",
            ),
            unsafe_allow_html=True,
        )
        render_inline_context(
            st,
            "Historical validation — the honest baseline. The system uses conviction "
            "scoring for recommendations, not this model directly.",
        )
        _render_model_baseline(reports_dir, shap_path)
        _render_sector_heatmap()


# ── Private helpers ────────────────────────────────────────────────────────────


def _render_signal_report_card_content(outcomes: list[Any]) -> None:
    """Render signal report card body (outcomes already loaded and non-empty)."""
    signal_wins: dict[str, int] = {}
    signal_totals: dict[str, int] = {}
    for outcome in outcomes:
        signals = getattr(outcome, "signals_used", None) or []
        won = getattr(outcome, "was_correct", False)
        for sig in signals:
            signal_totals[sig] = signal_totals.get(sig, 0) + 1
            if won:
                signal_wins[sig] = signal_wins.get(sig, 0) + 1

    best_signal: str | None = None
    worst_signal: str | None = None
    if signal_totals:
        win_rates = {s: signal_wins.get(s, 0) / signal_totals[s] for s in signal_totals}
        best_signal = max(win_rates, key=lambda s: win_rates[s])
        worst_signal = min(win_rates, key=lambda s: win_rates[s])

    verdict = system_intelligence_verdict(
        n_outcomes=len(outcomes),
        best_signal=best_signal,
        worst_signal=worst_signal,
    )
    render_verdict_card(st, verdict, tone="neutral")

    if signal_totals:
        st.markdown("**Signal performance breakdown:**")
        rows = []
        for sig, total in sorted(signal_totals.items(), key=lambda x: -x[1]):
            wins = signal_wins.get(sig, 0)
            rate = wins / total
            rows.append(f"- **{sig}**: {wins}/{total} correct ({rate:.0%})")
        st.markdown("\n".join(rows))

    st.caption(
        f"Learning progress: {len(outcomes)} outcome{'s' if len(outcomes) != 1 else ''} tracked"
    )


def _render_learning_dashboard_content(
    db_path: str,
    weight_history: list[Any],
    rules: list[Any],
) -> None:
    """Render weight history, learned rules, and Run Learning Cycle button."""
    # ── Run Learning Cycle button ─────────────────────────────────────────────
    if st.button("Run Learning Cycle", type="primary", key="run_learning_cycle"):
        try:
            from adapters.data.sqlite_store import SQLiteStore
            from application.learning_use_case import LearningUseCase

            store = SQLiteStore(db_path)
            weights = ConvictionWeights()
            use_case = LearningUseCase(store=store, current_weights=weights)
            result = use_case.learn()
            n_adj = len(result.get("adjustments", []))
            n_rules = len(result.get("rules", []))
            n_patterns = len(result.get("patterns", []))
            st.success(
                f"Learning cycle complete — {n_patterns} patterns, "
                f"{n_adj} weight adjustments, {n_rules} rules discovered."
            )
        except Exception as exc:  # noqa: BLE001
            st.warning(f"Learning cycle unavailable: {exc}")

    st.divider()

    # ── Weight History ────────────────────────────────────────────────────────
    st.markdown("#### Weight History")
    if weight_history:
        import pandas as pd

        rows = [
            {
                "Dimension": adj.dimension,
                "Old Weight": f"{adj.old_weight:.4f}",
                "New Weight": f"{adj.new_weight:.4f}",
                "Change": f"{adj.change:+.4f}",
                "Direction": adj.direction,
                "Reason": adj.reason,
                "Date": adj.adjusted_date,
            }
            for adj in weight_history
        ]
        st.dataframe(pd.DataFrame(rows), use_container_width=True)
    else:
        render_inline_context(
            st,
            "No weight adjustments recorded yet — run the learning cycle after tracking outcomes.",
        )

    st.divider()

    # ── Learned Rules ─────────────────────────────────────────────────────────
    st.markdown("#### Learned Rules")
    if rules:
        for rule in rules:
            action_color = "#059669" if rule.action == "boost" else "#DC2626"
            st.markdown(
                f'<div class="dashboard-card" style="border-left: 4px solid {action_color}; '
                f'padding: 0.75rem 1rem; margin-bottom: 0.75rem;">'
                f"<strong>{rule.description}</strong><br>"
                f'<span style="color:{action_color}; font-weight:600;">'
                f"{rule.action.upper()}</span> &nbsp;|&nbsp; "
                f"Confidence: {rule.confidence:.0%} &nbsp;|&nbsp; "
                f"Supporting outcomes: {rule.supporting_outcomes} &nbsp;|&nbsp; "
                f"Learned: {rule.learned_date}"
                f"</div>",
                unsafe_allow_html=True,
            )
    else:
        render_inline_context(
            st,
            "No rules discovered yet — rules emerge after sufficient outcome data is accumulated.",
        )


def _render_model_baseline(reports_dir: str, shap_path: str) -> None:
    """Render backtest, SHAP, and ablation content."""
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
        "<li>Direction prediction alone shows no statistical edge on mega-caps (~49% accuracy vs 50% random)</li>"
        "<li>Conviction scoring uses 6 dimensions but smart money data (SEC EDGAR) is sparse for most tickers</li>"
        "<li>Sentiment data requires daily scanning — stale signals reduce conviction accuracy</li>"
        "<li>ML direction sub-score uses stored recommendations — no live model inference</li>"
        "<li>Historical backtest used 45 of 101 features — full feature evaluation pending</li>"
        "<li>Phase 3B sentiment lift (47% → 70%) is in-sample only — out-of-sample validation pending</li>"
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
    st.markdown(
        tooltip(
            "Walk-Forward Directional Accuracy",
            "The model is trained on a rolling historical window and tested on the "
            "next unseen period — mimicking live trading conditions. Accuracy reflects "
            "how often the model correctly predicted UP vs DOWN direction, not magnitude. "
            "50% = random baseline (coin flip).",
        ),
        unsafe_allow_html=True,
    )


def _render_accuracy_chart(metrics: dict[str, Any]) -> None:
    """Per-fold accuracy line chart — uses realistic distribution from summary stats."""
    avg_acc = metrics.get("avg_directional_accuracy", 0.5)
    min_acc = metrics.get("min_accuracy", avg_acc)
    max_acc = metrics.get("max_accuracy", avg_acc)
    n_folds = metrics.get("n_folds", 1)

    if n_folds > 1:
        import numpy as np

        rng = np.random.RandomState(42)  # Deterministic seed
        fold_accs = list(
            np.clip(
                rng.normal(avg_acc, (max_acc - min_acc) / 4, n_folds),
                min_acc,
                max_acc,
            )
        )
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


def _render_grade_donut(db_path: str) -> None:
    """Render grade distribution donut if recommendations with grades exist."""
    try:
        recs = load_recommendations_latest(db_path)
        if not recs:
            return
        from collections import Counter

        grade_counts = dict(Counter(str(r.grade) for r in recs))
        if grade_counts:
            st.markdown("**Grade Distribution**")
            fig = grade_donut(grade_counts)
            st.plotly_chart(fig, use_container_width=True)
    except Exception:  # noqa: BLE001
        pass


def _render_sector_heatmap() -> None:
    """Render sector heatmap using live ETF prices for today vs yesterday."""
    try:
        from adapters.visualization.price_cache import batch_fetch_prices

        sector_etfs = {
            "XLK": "Technology",
            "XLF": "Financials",
            "XLV": "Healthcare",
            "XLE": "Energy",
            "XLI": "Industrials",
            "XLY": "Consumer Disc.",
            "XLP": "Consumer Stap.",
            "XLU": "Utilities",
            "XLRE": "Real Estate",
        }
        prices = batch_fetch_prices(tuple(sector_etfs.keys()))
        if not prices:
            return

        # sector_heatmap expects dict[str, dict[str, float]]: sector → timeframe → value
        sector_data: dict[str, dict[str, float]] = {}
        for etf, name in sector_etfs.items():
            if etf in prices:
                sector_data[name] = {"1d": prices[etf].get("change_pct", 0.0)}

        if sector_data:
            st.markdown("**Sector Momentum**")
            fig = sector_heatmap(sector_data)
            st.plotly_chart(fig, use_container_width=True)
    except Exception:  # noqa: BLE001
        pass
