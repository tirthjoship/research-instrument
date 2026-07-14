"""Trust tab — trophy grid, four rules, glossary, exhibits, and the one live experiment."""

from __future__ import annotations

import html as _html
import json
from pathlib import Path

import streamlit as st

from adapters.visualization.components.charts import (
    ablation_bar_chart,
    apply_dossier_template,
    shap_bar_chart,
)
from adapters.visualization.components.formatters import status_pill_html
from adapters.visualization.components.metrics import render_inline_context
from adapters.visualization.components.proof_tile import render_tile
from adapters.visualization.components.tooltip import tooltip
from adapters.visualization.components.verdicts import ablation_verdict
from adapters.visualization.data_loader import (
    load_ablation_results,
    load_shap_importance,
)

_SCOREBOARD = [
    {
        "hypothesis": "Does community conviction predict returns out of sample?",
        "short": "Community conviction",
        "test": "Pre-registered OOS conviction backtest",
        "verdict": "KILL",
        "adr": "docs/adr/039-conviction-validation-findings.md",
        "group": "external",
    },
    {
        "hypothesis": "Do conviction sub-dimensions carry independent signal?",
        "short": "Conviction sub-dimensions",
        "test": "Dimension-by-dimension IC audit",
        "verdict": "KILL",
        "adr": "docs/adr/043-conviction-dims-dead-divergence-led-surfacing.md",
        "group": "external",
    },
    {
        "hypothesis": "Does sentiment-vs-price divergence predict returns?",
        "short": "Sentiment/price divergence",
        "test": "Cross-sectional IC, clean 430-ticker universe",
        "verdict": "KILL",
        "adr": "docs/adr/044-divergence-ic-verdict.md",
        "group": "external",
    },
    {
        "hypothesis": "Do momentum exits beat buy-and-hold risk-adjusted?",
        "short": "Momentum-exit timing",
        "test": "Sharpe-difference bootstrap (CI spans 0)",
        "verdict": "KILL",
        "adr": "docs/adr/046-momentum-discipline-phase1-verdict.md",
        "group": "external",
    },
    {
        "hypothesis": "Does the evidence screen's top decile outperform?",
        "short": "Evidence-screen top decile",
        "test": "Screen IC forward test",
        "verdict": "INCONCLUSIVE",
        "adr": "docs/adr/049-decision-support-engine-architecture.md",
        "group": "methodology",
    },
    {
        "hypothesis": "Does a trend-following sleeve clear the pre-registered bar?",
        "short": "Trend-following sleeve",
        "test": "TSMOM sleeve backtest vs locked gate",
        "verdict": "INCONCLUSIVE",
        "adr": "docs/adr/050-trend-following-sleeve-verdict.md",
        "group": "methodology",
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

_VERDICT_MEANING = {
    "KILL": "This idea is dead — the app will never trade on it.",
    "INCONCLUSIVE": "Could not be proven — treated as dead until real evidence says otherwise.",
    "INCONCLUSIVE → practical KILL": "Could not be proven — treated as dead until real evidence says otherwise.",
    "PENDING": "Still accruing live evidence.",
}

# The four rules — ported verbatim from methodology.py _BODY (absorbed Task 7).
_FOUR_RULES = [
    {
        "title": "Pre-registration",
        "body": (
            "Before running any test we write down the exact pass/fail "
            "thresholds and lock them. If the result misses the bar, the idea dies — no "
            '"just tweak it and re-run."'
        ),
        "example": (
            "the insider-cluster test's pass/fail numbers were locked on June 9, 2026 "
            "— the verdict was read against them on June 10, unchanged."
        ),
    },
    {
        "title": "Point-in-time discipline",
        "body": (
            "Every prediction may only use data that existed at "
            "that moment. Using tomorrow's data to predict today is the most common way "
            "backtests lie; our code raises `LookAheadBiasError` if it ever happens."
        ),
        "example": (
            "it halts rather than let tomorrow's price leak into today's signal."
        ),
    },
    {
        "title": "Costs included",
        "body": (
            "A signal that looks profitable before trading costs and "
            "disappears after them is not an edge. We model the real cost of trading thin "
            "stocks (slippage) and test net of it."
        ),
        "example": (
            "the insider-cluster edge looked real gross of costs — and died when 150 bps "
            "of real-world trading cost was applied."
        ),
    },
    {
        "title": "Abstention over bravado",
        "body": (
            "When the evidence doesn't clear the bar, the tool "
            'says "no candidates" instead of guessing. Zero is an honest answer.'
        ),
        "example": (
            "the seven return-prediction hypotheses all failed testing — "
            "rather than lower the bar, each was retired. "
            "The app surfaces only attributed third-party signals, never its own return forecasts."
        ),
    },
]


def _unit_b_row(report_path: str) -> dict[str, str]:
    row: dict[str, str] = {
        "hypothesis": "Do insider buying clusters in sub-$1B names predict 21-day returns?",
        "short": "Insider clusters",
        "test": "Event study vs liquidity-matched ETF, pre-registered coverage guard",
        "verdict": "PENDING",
        "adr": "docs/adr/053-insider-cluster-falsification-verdict.md",
        "group": "methodology",
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


def _load_rank_ic(reports_dir: str) -> str:
    """Load mean_ic from the newest divergence_ic_1m_*.json (n_dates > 0).

    Returns formatted 3dp string, or ADR-044 recorded fallback "0.004".
    Does NOT read divergence_ic_21d.json (degenerate empty run).
    """
    p = Path(reports_dir)
    candidates = sorted(p.glob("divergence_ic_1m_*.json"), reverse=True)
    for f in candidates:
        try:
            data = json.loads(f.read_text())
            n_dates = int(data.get("n_dates", 0))
            if n_dates > 0:
                mean_ic = float(data["mean_ic"])
                return f"{mean_ic:.3f}"
        except (json.JSONDecodeError, OSError, KeyError, ValueError):
            continue
    return "0.004"


def _render_dead_architecture_stats(reports_dir: str = "data/reports") -> None:
    """Render the 2 stat tiles for the killed model_confidence architecture.

    Relocated from a top-of-page 3-tile hero (see git history / redesign spec
    2026-07-13) into "Dead architecture" since both stats describe the dead
    model, not the current app. The former 3rd tile ("Hypotheses retired
    N/7") was dropped as redundant — that count is already stated in the lead
    banner and the experiments synthesis sentence.
    """
    # ── Tile 1: Rank-IC ──────────────────────────────────────────────────────
    rank_ic_val = _load_rank_ic(reports_dir)
    rank_ic_label = tooltip("Rank-IC")

    # ── Tile 2: Directional accuracy ─────────────────────────────────────────
    ablation = load_ablation_results(reports_dir)
    dir_acc_val = "—"
    if ablation:
        for r in ablation:
            if "technical_only" in r.get("variant", ""):
                raw_acc = r.get("directional_accuracy")
                if raw_acc is not None:
                    dir_acc_val = f"{float(raw_acc):.1%}"
                break
    dir_acc_label = tooltip("Directional accuracy")

    cols = st.columns(2)
    with cols[0]:
        st.markdown(
            render_tile(
                label=rank_ic_label,
                number=rank_ic_val,
                stamp="FALSIFIED",
                tone="crimson",
                sub="the ranking signal knows ~nothing (ADR-044)",
            ),
            unsafe_allow_html=True,
        )
    with cols[1]:
        st.markdown(
            render_tile(
                label=dir_acc_label,
                number=dir_acc_val,
                stamp="= EMH",
                tone="muted",
                sub="no edge over a coin flip",
            ),
            unsafe_allow_html=True,
        )


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
    fig = apply_dossier_template(fig)
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
    st.markdown(
        f'<span style="font-size:11px;color:var(--ri-muted);">'
        f"{tooltip('Statistical significance (p-value)', label='ⓘ')} "
        'what "Significant" means here</span>',
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
        fig = apply_dossier_template(fig)
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.caption("No SHAP data — run SHAP analysis to populate.")


def _experiment_synthesis(n_dead: int, n_open: int) -> str:
    """PROTOTYPE — one-line pattern across the 7 experiments, not just a flat list."""
    return (
        f"<strong>The pattern:</strong> {n_dead} of 7 are confirmed dead — external "
        "predictive signals and trading rules (community conviction, sentiment "
        "divergence, momentum-exit timing, insider clusters) that didn't survive "
        f"out-of-sample testing. The remaining {n_open} are about the app's own "
        "evidence-screening methodology itself, still resolving — not yet proven, "
        "not yet killed."
    )


def _verdict_rule_color(verdict: str) -> str:
    """Map a verdict string to its accent color (crimson/amber/muted)."""
    leading_token = verdict.split()[0]
    if leading_token == "KILL" or verdict == "INCONCLUSIVE → practical KILL":
        return "#DC2626"
    if leading_token == "INCONCLUSIVE":
        return "#CA8A04"
    return "#64748B"


def _scoreboard_strip_html(rows: list[dict[str, str]]) -> str:
    """One-glance color strip (color only, no in-block text) + a legend line.

    Color-only blocks avoid the KILL/"?"/"•" labeling mismatch a text-mixed strip
    would have — a plain legend above spells out what each color means once.
    """
    legend_items = [
        ("#DC2626", "KILL — dead, will never trade"),
        ("#CA8A04", "INCONCLUSIVE — unproven, resolving"),
        ("#64748B", "PENDING — live, still accruing evidence"),
    ]
    legend = "".join(
        f'<span style="display:inline-flex;align-items:center;gap:5px;">'
        f'<i style="background:{color};width:10px;height:10px;border-radius:2px;'
        f'display:inline-block;"></i>{text}</span>'
        for color, text in legend_items
    )
    blocks = "".join(
        f'<div style="flex:1;height:30px;border-radius:6px;'
        f'background:{_verdict_rule_color(r["verdict"])};"></div>'
        for r in rows
    )
    return (
        f'<div style="display:flex;gap:16px;font-size:11px;color:var(--ri-muted);'
        f'margin:8px 0 10px;flex-wrap:wrap;">{legend}</div>'
        f'<div style="display:flex;gap:4px;margin-bottom:10px;">{blocks}</div>'
    )


def _render_experiment_row(r: dict[str, str]) -> None:
    """One experiment as a compact expander: verdict + claim visible, full
    Claim→Test→Result→Decision detail on click, colored left accent bar."""
    verdict = r["verdict"]
    leading_token = verdict.split()[0]
    rule_color = _verdict_rule_color(verdict)
    decision = _VERDICT_MEANING.get(verdict, _VERDICT_MEANING.get(leading_token, ""))

    label = f"**{verdict}** — {r['hypothesis']}"
    with st.expander(label):
        st.markdown(
            f'<div style="border-left:4px solid {rule_color};padding-left:10px;'
            f'font-size:13px;line-height:1.7;">'
            f"<b>Test:</b> {r['test']}<br>"
            f'<b>Result:</b> <span style="color:{rule_color};font-weight:700;">{verdict}</span><br>'
            f"<b>Decision:</b> <i>{decision}</i></div>",
            unsafe_allow_html=True,
        )
        st.caption(f"`{r['adr']}`")


def _decision_tree_html(rows: list[dict[str, str]]) -> str:
    """Branching diagram of the actual verdict logic, naming which experiment
    landed on each branch — not just an aggregate count (which only repeated
    the scoreboard strip in a different shape). Additive to the strip: the
    strip gives the one-glance color pattern, this explains *why* each
    specific experiment landed where it did, including the honest fact that
    no hypothesis has ever cleared the bar. Wrapped in a card so it reads as
    a section of the page, not a floating diagram.
    """
    n_total = len(rows)
    kill_names = [
        r["short"] for r in rows if _verdict_rule_color(r["verdict"]) == "#DC2626"
    ]
    inconclusive_names = [
        r["short"] for r in rows if _verdict_rule_color(r["verdict"]) == "#CA8A04"
    ]
    pending_names = [
        r["short"] for r in rows if _verdict_rule_color(r["verdict"]) == "#64748B"
    ]

    def _node(text: str) -> str:
        return (
            f'<div style="display:flex;justify-content:center;margin-bottom:6px;">'
            f'<div style="background:var(--ri-app);border:1px solid var(--ri-line);'
            f"border-radius:8px;padding:9px 14px;font-size:12px;text-align:center;"
            f'color:var(--ri-ink);font-weight:600;">{text}</div></div>'
        )

    def _leaf(
        bg: str,
        border: str,
        color: str,
        heading: str,
        names: list[str],
        dashed: bool = False,
    ) -> str:
        style = "dashed" if dashed else "solid"
        names_html = (
            "<br>".join(_html.escape(n) for n in names) if names else "none right now"
        )
        return (
            f'<div style="background:{bg};border:1px {style} {border};'
            f"border-radius:8px;padding:9px 12px;font-size:11px;text-align:center;"
            f'min-width:150px;color:{color};flex:1;">{heading}'
            f'<div style="margin-top:6px;font-size:10.5px;line-height:1.5;">{names_html}</div>'
            "</div>"
        )

    arrow = (
        '<div style="text-align:center;color:var(--ri-muted);font-size:13px;">↓</div>'
    )

    diagram = (
        _node(
            "Pre-registration "
            '<span style="font-weight:400;font-size:10.5px;color:var(--ri-muted);">'
            "— pass/fail bar locked before any test runs</span>"
        )
        + arrow
        + _node(
            "Out-of-sample test, point-in-time data only "
            '<span style="font-weight:400;font-size:10.5px;color:var(--ri-muted);">'
            "— LookAheadBiasError halts on violation</span>"
        )
        + arrow
        + _node("Clears the locked bar, net of trading costs?")
        + '<div style="display:flex;gap:10px;margin-top:10px;flex-wrap:wrap;">'
        + _leaf(
            "#FEF2F2",
            "#FCA5A5",
            "#991B1B",
            f"No → <b>KILL</b> ({len(kill_names)}/{n_total})",
            kill_names,
        )
        + _leaf(
            "#FFFBEB",
            "#FDE68A",
            "#92400E",
            f"Underpowered / ambiguous → <b>INCONCLUSIVE</b> ({len(inconclusive_names)}/{n_total})",
            inconclusive_names,
        )
        + _leaf(
            "var(--ri-app)",
            "var(--ri-line)",
            "var(--ri-ink2)",
            f"Still accruing evidence → <b>PENDING</b> ({len(pending_names)}/{n_total})",
            pending_names,
        )
        + _leaf(
            "var(--ri-app)",
            "var(--ri-line)",
            "var(--ri-muted)",
            "Yes → <b>would advance to a live signal</b>",
            [],
            dashed=True,
        )
        + "</div>"
    )
    return (
        '<div style="background:var(--ri-card);border:1px solid var(--ri-line);'
        'border-radius:16px;padding:18px 20px;margin-bottom:16px;">'
        f"{diagram}"
        f'<div style="text-align:center;font-size:10.5px;color:var(--ri-muted);'
        f'margin-top:8px;">0/{n_total} hypotheses have ever reached the "yes" branch.</div>'
        "</div>"
    )


def _render_trophy_grid(report_path: str) -> None:
    """Render the scoreboard strip, then experiment rows grouped by kind:
    external signals (all killed) vs our own methodology (still resolving).

    Each row is a compact expander — verdict + claim always visible (scannable
    at a glance), full Claim→Test→Result→Decision detail on click.
    """
    rows = _SCOREBOARD + [_unit_b_row(report_path)]
    st.markdown(_scoreboard_strip_html(rows), unsafe_allow_html=True)

    external_rows = [r for r in rows if r["group"] == "external"]
    methodology_rows = [r for r in rows if r["group"] == "methodology"]

    col_ext, col_meth = st.columns(2)
    with col_ext:
        st.markdown(
            '<div class="ri-lab" style="margin-bottom:8px;">'
            "External signals — all killed</div>",
            unsafe_allow_html=True,
        )
        for r in external_rows:
            _render_experiment_row(r)
    with col_meth:
        st.markdown(
            '<div class="ri-lab" style="margin-bottom:8px;">'
            "Our own methodology — resolving</div>",
            unsafe_allow_html=True,
        )
        for r in methodology_rows:
            _render_experiment_row(r)

    st.markdown(
        '<div class="ri-lab" style="margin:16px 0 8px;">'
        "The decision logic — why each verdict happened</div>",
        unsafe_allow_html=True,
    )
    st.markdown(_decision_tree_html(rows), unsafe_allow_html=True)


def _pipeline_diagram_html() -> str:
    """Static linear flow diagram — pure illustration, no data dependency.

    Sits next to the four rules that describe this process. A separate,
    simpler diagram from the Experiments decision tree, which explains the
    branching *outcome* logic instead.
    """
    steps = ["Pre-registration", "Point-in-time gate", "Cost model", "Verdict"]
    arrow = '<div style="color:var(--ri-muted);font-size:16px;padding:0 6px;">→</div>'
    boxes = []
    for i, step in enumerate(steps):
        is_last = i == len(steps) - 1
        bg = "#FEF2F2" if is_last else "var(--ri-card)"
        border = "#FCA5A5" if is_last else "var(--ri-line)"
        boxes.append(
            f'<div style="flex:1;background:{bg};border:1px solid {border};'
            f"border-radius:8px;padding:10px 8px;text-align:center;font-size:11px;"
            f'font-weight:600;color:var(--ri-ink);">{step}</div>'
        )
    row = arrow.join(boxes)
    return (
        f'<div style="display:flex;align-items:center;gap:6px;margin-bottom:14px;">'
        f"{row}</div>"
    )


def _render_four_rules() -> None:
    """Header + anchor stay always visible (other tabs assume #tr-honest
    exists); the pipeline diagram + rule cards collapse behind one click —
    2026-07-14 trim, page was too long for a fast skim.
    """
    st.markdown(
        '<div id="tr-honest" style="font-weight:700;font-size:16px;margin-bottom:8px;">'
        "How this project keeps itself honest"
        "</div>",
        unsafe_allow_html=True,
    )
    with st.expander("The pipeline + the four rules"):
        st.markdown(_pipeline_diagram_html(), unsafe_allow_html=True)
        rule_pairs = [_FOUR_RULES[i : i + 2] for i in range(0, len(_FOUR_RULES), 2)]
        for pair in rule_pairs:
            rule_cols = st.columns(2)
            for col, rule in zip(rule_cols, pair):
                idx = _FOUR_RULES.index(rule) + 1
                chip_html = (
                    f'<span class="section-chip">{idx}</span> '
                    f'<strong>{rule["title"]}</strong>'
                )
                card_html = (
                    f'<div style="background:var(--ri-card);border:1px solid var(--ri-line);'
                    f'border-radius:16px;padding:14px 18px;margin-bottom:12px;">'
                    f"{chip_html}<br>"
                    f'<span style="font-size:14px;">{rule["body"]}</span><br>'
                    f'<span style="color:var(--ri-muted);font-size:13px;font-style:italic;">'
                    f'Example: {rule["example"]}'
                    f"</span></div>"
                )
                with col:
                    st.markdown(card_html, unsafe_allow_html=True)


def _gate_strip(log_path: str) -> None:
    st.markdown('<div id="tr-live"></div>', unsafe_allow_html=True)
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


# "Is this real work?" section: proof of actual data-science depth, as stamp
# tiles (label, big number, one-line detail) reusing proof_tile — the same
# component the old top-of-page hero used, repurposed here since this section
# is where the "wow" moment belongs. Each number is independently verifiable
# in the repo.
_UNDER_THE_HOOD: list[tuple[str, str, str]] = [
    (
        "ML ADAPTER MODULES",
        "22",
        "XGBoost + LightGBM + Ridge ensemble, Flan-T5 sentiment, 45 features "
        "across 8 groups.",
    ),
    (
        "BOOTSTRAP ITERATIONS",
        "500",
        "CI on every risk stat; dollar-interpretable Ridge; VIF checks; real "
        "Fama-French 5-factor data.",
    ),
    (
        "DATED DECISION TRAIL",
        "52",
        "ADRs — including every kill decision below. LookAheadBiasError halts "
        "point-in-time violations.",
    ),
    (
        "PRE-REGISTERED BACKTESTS",
        "4",
        "Conviction, momentum-exit, trend-sleeve, screen — each graded on "
        "Sharpe, not raw returns.",
    ),
]


def _render_under_the_hood() -> None:
    st.markdown(
        '<div class="ri-sec" id="tr-hood">Is this real work? — the infrastructure '
        "behind the numbers</div>",
        unsafe_allow_html=True,
    )
    cols = st.columns(4)
    for col, (label, number, sub) in zip(cols, _UNDER_THE_HOOD):
        with col:
            st.markdown(
                render_tile(label=label, number=number, tone="muted", sub=sub),
                unsafe_allow_html=True,
            )


def _scoreboard_counts(report_path: str) -> tuple[int, int]:
    """(n_dead, n_total) across the static scoreboard + live unit-B row.

    Shared by the hero tile and the plain-English lead sentence so they
    never disagree on the count.
    """
    all_rows = list(_SCOREBOARD) + [_unit_b_row(report_path)]
    n_total = len(all_rows)
    n_dead = sum(
        1
        for r in all_rows
        if r["verdict"].startswith("KILL")
        or r["verdict"] == "INCONCLUSIVE → practical KILL"
    )
    return n_dead, n_total


def _trust_nav() -> str:
    """PROTOTYPE — quick-jump chips, single-level (no filtering, jump-scroll only)."""
    chips = [
        ("#tr-hood", "Is this real work?", "The infrastructure ↓", "#2563EB"),
        ("#tr-tested", "See the 7 experiments", "Claim → Test → Result ↓", "#DC2626"),
        ("#tr-honest", "How we stay honest", "The four rules ↓", "#0F6E80"),
        ("#tr-live", "What's still live", "The one open experiment ↓", "#CA8A04"),
        ("#tr-raw", "Dead architecture", "Old exhibits + raw metrics ↓", "#64748B"),
    ]
    items = "".join(
        f'<a href="{href}" class="tr-nav" style="flex:1;min-width:150px;text-decoration:none;'
        f"background:var(--bg-primary);border:1px solid var(--border);border-radius:11px;"
        f'padding:11px 13px;border-left:4px solid {color};">'
        f"<div style=\"font-family:'Fraunces',serif;font-weight:800;font-size:15px;color:var(--text-primary);\">{label}</div>"
        f"<div style=\"font-family:'IBM Plex Mono',monospace;font-size:9.5px;letter-spacing:.08em;"
        f'text-transform:uppercase;color:#64748B;margin-top:3px">{sub}</div></a>'
        for href, label, sub, color in chips
    )
    return f'<div style="display:flex;gap:8px;flex-wrap:wrap;margin-bottom:16px;">{items}</div>'


def _header_html() -> str:
    """Page title + lead line, matching Home/Risk/Portfolio's ri-h1/ri-sub pair."""
    return (
        '<div class="ri-h1">Trust</div>'
        '<div class="ri-sub">Every prediction idea we tested and the verdicts — '
        "the receipts behind the app's honesty.</div>"
    )


def _lead_banner_html(n_total: int, n_dead: int, n_open: int) -> str:
    """Plain-English lead banner: bottom line -> why credible -> bridge to other tabs.

    Uses the same --ri-card/--ri-line tokens as .ri-tile instead of the legacy
    .ws-card class, so the card visually matches Risk/Portfolio's info cards.
    """
    return (
        '<div style="background:var(--ri-card);border:1px solid var(--ri-line);'
        'border-radius:16px;padding:16px 20px;margin-bottom:16px;">'
        f"<strong>We tested {n_total} ways to predict stock moves. {n_dead} are dead, "
        f"{n_open} remain unproven — we're not chasing an {n_total + 1}th. Instead we "
        "show you real, attributed facts and let you judge them yourself.</strong><br>"
        '<span style="color:var(--ri-muted);font-size:14px;">'
        "Every test's pass/fail line was locked before we saw the results, so a failure "
        "is real — not a re-roll. This same discipline — real data only, no hindsight, "
        "no cherry-picking — is what backs every number you see on Screener, Risk, and "
        "Stock Analysis."
        "</span></div>"
    )


def _render_dead_architecture_details() -> None:
    """Old-architecture stats + exhibits, one expander, both charts side-by-side.

    2026-07-14 trim: folded the 2 stat tiles (previously always-visible above
    this expander) inside it, alongside the exhibits — both are about the
    same killed model_confidence architecture, so grouping them behind one
    click reduces always-on-screen height without losing any content.
    Exhibits themselves are one level deep (not nested sub-expanders): both
    charts, including the SHAP chart, render immediately on first expand.
    """
    with st.expander("Old metrics + falsified-era exhibits (kept for the record)"):
        _render_dead_architecture_stats()
        col_a, col_b = st.columns(2)
        with col_a:
            st.markdown(
                "**Exhibit A: Ablation analysis (FALSIFIED era)** "
                f"{tooltip('Ablation study', label='ⓘ')}",
                unsafe_allow_html=True,
            )
            _render_ablation_exhibit()
        with col_b:
            st.markdown(
                "**Exhibit B: SHAP feature importance (FALSIFIED era)** "
                f"{tooltip('SHAP value', label='ⓘ')}",
                unsafe_allow_html=True,
            )
            _render_shap_exhibit()


def render(
    report_path: str = "data/reports/insider_cluster_falsification_2024.json",
    log_path: str = "data/personal/discipline_log.jsonl",
) -> None:
    st.markdown(_header_html(), unsafe_allow_html=True)

    # PROTOTYPE — quick-jump nav, single-level, jump-scroll only (nothing hidden below)
    st.markdown(_trust_nav(), unsafe_allow_html=True)

    n_dead, n_total = _scoreboard_counts(report_path)
    n_open = n_total - n_dead
    st.markdown(
        _lead_banner_html(n_total=n_total, n_dead=n_dead, n_open=n_open),
        unsafe_allow_html=True,
    )

    # PROTOTYPE — "Is this real work?": proof of actual infrastructure, right after
    # the lead so it answers "is this just a UI" before the failure list even starts.
    _render_under_the_hood()

    st.divider()

    # PROTOTYPE — synthesis sentence naming the pattern across the 7 experiments,
    # before the compact expander list (was: no synthesis, 7 flat identical cards).
    st.markdown(
        '<div class="ri-sec" id="tr-tested">Experiments — what was tested and what happened</div>',
        unsafe_allow_html=True,
    )
    st.markdown(
        f'<div style="font-size:13.5px;line-height:1.6;margin-bottom:10px;">'
        f"{_experiment_synthesis(n_dead, n_open)}</div>",
        unsafe_allow_html=True,
    )
    _render_trophy_grid(report_path)

    st.divider()

    # The four rules — ported from methodology.py, 2×2 grid of ws-cards
    _render_four_rules()

    st.divider()

    # The one live/ongoing experiment, ahead of the falsified-era exhibits since
    # it's current, not archival.
    _gate_strip(log_path)

    st.divider()

    # Exhibits from model_confidence era — kept with honesty banners, collapsed.
    # PROTOTYPE — framing sentence: this is a DIFFERENT (dead) architecture from
    # the current one shown in "Is this real work?" above, kept for honesty, not
    # because it's still how the app works.
    st.markdown(
        '<div class="ri-sec" id="tr-raw">Dead architecture — old metrics, exhibits, glossary</div>',
        unsafe_allow_html=True,
    )
    st.caption(
        "An earlier architecture (model_confidence) was tested and killed the same "
        "way as everything above — kept here, not deleted, because honesty means "
        "showing dead work too, not just curating a highlight reel."
    )
    _render_dead_architecture_details()

    st.divider()

    # Glossary reference
    with st.expander("Glossary — every term in plain English"):
        import pandas as pd

        from adapters.visualization.components.glossary import GLOSSARY

        st.dataframe(
            pd.DataFrame(GLOSSARY.items(), columns=["Term", "Meaning"]),
            hide_index=True,
            use_container_width=True,
        )

    # Smooth-scroll shim for the quick-jump nav chips above (see lens_scroll.py)
    from adapters.visualization.components.lens_scroll import render_lens_scroll

    render_lens_scroll(
        selector="a.tr-nav", count=5, component_name="scr_trust_nav_scroll"
    )
