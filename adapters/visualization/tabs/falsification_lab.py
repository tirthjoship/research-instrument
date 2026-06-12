"""Falsification Lab — the verdict scoreboard, exhibits, and the one live experiment."""

from __future__ import annotations

import json
from pathlib import Path

import streamlit as st

from adapters.visualization.components.charts import ablation_bar_chart, shap_bar_chart
from adapters.visualization.components.formatters import status_pill_html
from adapters.visualization.components.metrics import render_inline_context
from adapters.visualization.components.verdicts import ablation_verdict
from adapters.visualization.data_loader import (
    load_ablation_results,
    load_shap_importance,
)

_SCOREBOARD = [
    {
        "hypothesis": "Does community conviction predict returns out of sample?",
        "test": "Pre-registered OOS conviction backtest",
        "verdict": "KILL",
        "adr": "docs/adr/039-conviction-validation-findings.md",
    },
    {
        "hypothesis": "Do conviction sub-dimensions carry independent signal?",
        "test": "Dimension-by-dimension IC audit",
        "verdict": "KILL",
        "adr": "docs/adr/043-conviction-dims-dead-divergence-led-surfacing.md",
    },
    {
        "hypothesis": "Does sentiment-vs-price divergence predict returns?",
        "test": "Cross-sectional IC, clean 430-ticker universe",
        "verdict": "KILL",
        "adr": "docs/adr/044-divergence-ic-verdict.md",
    },
    {
        "hypothesis": "Do momentum exits beat buy-and-hold risk-adjusted?",
        "test": "Sharpe-difference bootstrap (CI spans 0)",
        "verdict": "KILL",
        "adr": "docs/adr/046-momentum-discipline-phase1-verdict.md",
    },
    {
        "hypothesis": "Does the evidence screen's top decile outperform?",
        "test": "Screen IC forward test",
        "verdict": "INCONCLUSIVE",
        "adr": "docs/adr/049-decision-support-engine-architecture.md",
    },
    {
        "hypothesis": "Does a trend-following sleeve clear the pre-registered bar?",
        "test": "TSMOM sleeve backtest vs locked gate",
        "verdict": "INCONCLUSIVE",
        "adr": "docs/adr/050-trend-following-sleeve-verdict.md",
    },
]

_VERDICT_COLOR = {
    "KILL": "#DC2626",
    "INCONCLUSIVE": "#CA8A04",
    "PASS": "#16A34A",
    "PENDING": "#64748B",
}

# Unit B's report verdict string is INCONCLUSIVE_THIN_COVERAGE (validated against
# data/reports/insider_cluster_falsification_2024.json, 2026-06-11). Per ADR-053
# this resolved to a PRACTICAL KILL via the survivorship-honest coverage guard.
_VERDICT_DISPLAY = {
    "INCONCLUSIVE_THIN_COVERAGE": ("INCONCLUSIVE → practical KILL", "INCONCLUSIVE"),
}


def _unit_b_row(report_path: str) -> dict[str, str]:
    row: dict[str, str] = {
        "hypothesis": "Do insider buying clusters in sub-$1B names predict 21-day returns?",
        "test": "Event study vs liquidity-matched ETF, pre-registered coverage guard",
        "verdict": "PENDING",
        "adr": "docs/adr/053-insider-cluster-falsification-verdict.md",
    }
    p = Path(report_path)
    if p.exists():
        try:
            raw = str(json.loads(p.read_text()).get("verdict", "PENDING"))
            label, _ = _VERDICT_DISPLAY.get(raw, (raw, raw))
            row["verdict"] = label
        except (json.JSONDecodeError, OSError):
            pass
    return row


def _render_ablation_exhibit(reports_dir: str = "data/reports") -> None:
    st.caption("FALSIFIED-era artifact — kept as exhibit")
    ablation = load_ablation_results(reports_dir)
    if not ablation:
        render_inline_context(
            st, "No ablation data — run Phase 3B validation to populate."
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

    render_inline_context(st, ablation_verdict(tech_acc, combined_acc))
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
        st.markdown(
            f"{r.get('variant', '?').replace('_', ' ').title()}: {pill}",
            unsafe_allow_html=True,
        )


def _render_shap_exhibit(shap_path: str = "data/reports/shap_importance.json") -> None:
    st.caption("FALSIFIED-era artifact — kept as exhibit")
    render_inline_context(
        st, "Which features drove predictions? Colored by signal layer."
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
        st.caption("No SHAP data — run SHAP analysis to populate.")


def _gate_strip(log_path: str) -> None:
    p = Path(log_path)
    if not p.exists():
        st.caption("Forward gate: no discipline log yet.")
        return
    dates: set[str] = set()
    for line in p.read_text().splitlines():
        try:
            dates.add(json.loads(line).get("as_of", "")[:10])
        except json.JSONDecodeError:
            continue
    dates.discard("")
    st.markdown("**The one live experiment — discipline forward gate (ADR-048/051)**")
    # Targets validated against application/calibration_readiness.py (2026-06-11):
    # k_dates=3 distinct dates >=10 days apart, n_min=30 resolved flags. Rendered
    # as static text — the dashboard never recomputes readiness (domain logic
    # stays in the discipline-calibration-status CLI).
    st.caption(
        f"{len(dates)} weekly review dates accrued · gate needs ≥30 resolved "
        "REDUCE flags across ≥3 dates ≥10 days apart (ADR-051) · resolves "
        "~mid-July 2026 — evidence accrues weekly with zero code changes."
    )


def render(
    report_path: str = "data/reports/insider_cluster_falsification_2024.json",
    log_path: str = "data/personal/discipline_log.jsonl",
) -> None:
    st.subheader("Falsification Lab")
    st.markdown(
        "Most dashboards show what works. This one also shows what **doesn't** — "
        "every hypothesis below was tested with thresholds locked **before** "
        "seeing results (pre-registration), so a kill is a kill."
    )

    rows = _SCOREBOARD + [_unit_b_row(report_path)]
    for r in rows:
        # Color by the leading verdict token so display labels like
        # "INCONCLUSIVE → practical KILL" still resolve to the amber key.
        color = _VERDICT_COLOR.get(r["verdict"].split()[0], "#64748B")
        st.markdown(
            f'<div class="ws-card" style="border-left:4px solid {color};'
            f'padding:10px 16px;margin-bottom:8px;">'
            f'<span style="color:{color};font-weight:700;">{r["verdict"]}</span> — '
            f'<strong>{r["hypothesis"]}</strong><br>'
            f'<span style="color:#64748B;font-size:13px;">'
            f'_{r["test"]}_ · <code>{r["adr"]}</code></span>'
            "</div>",
            unsafe_allow_html=True,
        )

    st.divider()

    # Exhibits from model_confidence era — kept with honesty banners
    with st.expander("Exhibit A: Ablation analysis (FALSIFIED era)"):
        _render_ablation_exhibit()

    with st.expander("Exhibit B: SHAP feature importance (FALSIFIED era)"):
        _render_shap_exhibit()

    st.divider()
    _gate_strip(log_path)
