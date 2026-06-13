"""Risk tab — Unit A macro-beta scrubber, promoted from CLI markdown."""

from __future__ import annotations

import plotly.graph_objects as go
import streamlit as st

from adapters.visualization.components.charts import apply_dossier_template
from adapters.visualization.components.metrics import render_verdict_card
from adapters.visualization.components.tooltip import tooltip
from adapters.visualization.data_loader import load_brief_summary

_FLAG_MEANING = {
    "SYSTEMATIC_DOMINANT": (
        "Most of the book's movement is one market-wide bet, not stock picking.",
        "Adding 'one more name' will not diversify this — only a different asset class or hedge changes it.",
    ),
    "FACTOR_DOMINANCE": (
        "One macro factor (e.g. the market or rates) explains an outsized share of risk.",
        "Check whether you MEANT to make that macro bet; trim names that all load on it if not.",
    ),
    "DRIFT": (
        "The book's factor mix moved materially since the last review.",
        "Re-read the latest weekly brief and confirm the new tilt is intentional.",
    ),
}


def render(path: str = "data/personal/brief_summary.json") -> None:
    st.subheader("Portfolio Risk — Macro-Beta Scrubber")
    st.markdown(
        '<div style="color:#64748B;font-size:14px;margin-bottom:16px;">'
        "Where your book's risk actually comes from, in plain English."
        "</div>",
        unsafe_allow_html=True,
    )
    st.caption("Heuristic surfacing dials, not validated edges (ADR-052).")

    summary = load_brief_summary(path)
    macro = (summary or {}).get("macro")
    if macro is None:
        st.warning(
            "No macro-beta data. Run `python -m application.cli weekly-brief` "
            "(the scrubber runs inside it)."
        )
        return

    betas: dict[str, float] = macro.get("net_beta_by_factor", {})
    dominant = macro.get("dominant_factor")
    sys_share = float(macro.get("systematic_share", 0.0))

    # Hero metrics row — big numbers with plain-English glossary tooltips
    spy_beta = betas.get("SPY")
    beta_str = f"{spy_beta:+.2f}" if spy_beta is not None else "n/a"
    st.markdown(
        '<div class="ri-metric-row">'
        f'<div class="ri-metric"><div class="ri-metric-lab">'
        f"{tooltip('Net beta', 'Net market beta (SPY)')}</div>"
        f'<div class="ri-metric-num">{beta_str}</div></div>'
        f'<div class="ri-metric"><div class="ri-metric-lab">'
        f"{tooltip('Systematic share')}</div>"
        f'<div class="ri-metric-num">{sys_share:.0%}</div></div>'
        f'<div class="ri-metric"><div class="ri-metric-lab">'
        f"{tooltip('Concentrated risk', 'Dominant factor')}</div>"
        f'<div class="ri-metric-num">{dominant or "none"}</div></div>'
        "</div>",
        unsafe_allow_html=True,
    )

    st.divider()

    # Factor bars and donut side-by-side
    chart_col, donut_col = st.columns(2)

    with chart_col:
        st.markdown('<div class="ri-sec">FACTOR EXPOSURE</div>', unsafe_allow_html=True)
        if betas:
            fig = go.Figure(
                go.Bar(
                    x=list(betas.keys()),
                    y=list(betas.values()),
                    marker_color=[
                        "#CE2F26" if v < 0 else "#0F6E80" for v in betas.values()
                    ],
                )
            )
            fig.add_hline(
                y=1.0,
                line_dash="dot",
                line_color="#717885",
                annotation_text="moves 1:1 with market",
                annotation_font_size=11,
            )
            apply_dossier_template(fig)
            fig.update_layout(
                title="Dollar-weighted net beta by factor",
                xaxis_title="Factor",
                yaxis_title="Net beta",
                height=320,
                showlegend=False,
            )
            st.plotly_chart(fig, use_container_width=True, height=300)
            if spy_beta is not None:
                st.caption(f"Your book moves about {spy_beta:.2f}× the market.")

    with donut_col:
        st.markdown('<div class="ri-sec">RISK SOURCES</div>', unsafe_allow_html=True)
        # Systematic vs idiosyncratic donut
        idio_share = max(0.0, 1.0 - sys_share)
        donut = go.Figure(
            go.Pie(
                labels=["Systematic (macro)", "Idiosyncratic (stock-specific)"],
                values=[sys_share, idio_share],
                hole=0.55,
                marker_colors=["#0F6E80", "#1F9254"],
            )
        )
        apply_dossier_template(donut)
        donut.update_layout(
            title="Where the book's risk comes from",
            showlegend=True,
            height=320,
        )
        st.plotly_chart(donut, use_container_width=True, height=300)

    # Plain-English conclusion band
    if dominant is not None and sys_share > 0:
        conclusion_text = (
            f"{sys_share:.0%} of your book's swings trace to one market-wide "
            f"bet ({dominant}) — adding another same-direction name will not "
            f"diversify this."
        )
    else:
        conclusion_text = (
            "DATA_GAP: systematic-share or dominant-factor missing — "
            "run `python -m application.cli weekly-brief` to populate."
        )
    st.markdown(
        f'<div class="ri-conclusion">{conclusion_text}</div>',
        unsafe_allow_html=True,
    )

    # Flag cards
    flags = macro.get("flags", [])
    if flags:
        st.markdown("**Risk flags**")
        for flag in flags:
            meaning, action = _FLAG_MEANING.get(
                flag,
                ("Unrecognized flag.", "See the weekly brief markdown for detail."),
            )
            render_verdict_card(
                st,
                verdict=flag,
                tone="negative",
                details=f"{meaning} — {action}",
            )

    st.caption(
        f"Coverage: {macro.get('coverage_holdings', '?')}/{macro.get('total_holdings', '?')} holdings."
    )
