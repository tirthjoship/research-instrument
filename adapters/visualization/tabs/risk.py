"""Risk tab — Unit A macro-beta scrubber, promoted from CLI markdown."""

from __future__ import annotations

import plotly.graph_objects as go
import streamlit as st

from adapters.visualization.components.metrics import render_verdict_card
from adapters.visualization.data_loader import load_brief_summary

_PLOTLY_LAYOUT = {
    "font": {"family": "Inter, sans-serif"},
    "paper_bgcolor": "rgba(0,0,0,0)",
    "plot_bgcolor": "rgba(0,0,0,0)",
    "height": 320,
    "colorway": ["#2563EB", "#64748B", "#16A34A", "#DC2626", "#CA8A04"],
    "showlegend": False,
    "margin": {"l": 40, "r": 20, "t": 40, "b": 40},
}

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

    # Hero metrics row
    cols = st.columns(3)
    spy_beta = betas.get("SPY")
    cols[0].metric(
        "Net market beta (SPY)", f"{spy_beta:+.2f}" if spy_beta is not None else "n/a"
    )
    cols[1].metric("Systematic share", f"{sys_share:.0%}")
    cols[2].metric("Dominant factor", dominant or "none")

    st.divider()

    # Factor bars
    if betas:
        fig = go.Figure(
            go.Bar(
                x=list(betas.keys()),
                y=list(betas.values()),
                marker_color=[
                    "#DC2626" if v < 0 else "#2563EB" for v in betas.values()
                ],
            )
        )
        fig.update_layout(
            title="Dollar-weighted net beta by factor",
            xaxis_title="Factor",
            yaxis_title="Net beta",
            **_PLOTLY_LAYOUT,
        )
        st.plotly_chart(fig, use_container_width=True)

    # Systematic vs idiosyncratic donut
    idio_share = max(0.0, 1.0 - sys_share)
    donut = go.Figure(
        go.Pie(
            labels=["Systematic (macro)", "Idiosyncratic (stock-specific)"],
            values=[sys_share, idio_share],
            hole=0.55,
            marker_colors=["#2563EB", "#16A34A"],
        )
    )
    donut.update_layout(
        title="Where the book's risk comes from",
        showlegend=True,
        **{k: v for k, v in _PLOTLY_LAYOUT.items() if k != "showlegend"},
    )
    st.plotly_chart(donut, use_container_width=True)

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
