"""Dashboard entry point — 7-tab honest cockpit."""

from __future__ import annotations

import streamlit as st

st.set_page_config(
    page_title="Stock Intelligence",
    page_icon=None,
    layout="wide",
    initial_sidebar_state="collapsed",
)

from adapters.visualization.components.styles import inject_global_css  # noqa: E402

inject_global_css()

st.markdown(
    "<h1 style=\"margin-bottom:2px;font-family:'DM Sans',sans-serif;\">Multi-Modal Stock Recommender</h1>",
    unsafe_allow_html=True,
)

tab0, tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs(
    [
        "Weekly Brief",
        "Research Candidates",
        "Risk",
        "My Portfolio",
        "Stock Analysis",
        "Falsification Lab",
        "Methodology",
    ]
)

with tab0:
    from adapters.visualization.tabs.weekly_brief import render as render_brief

    render_brief()
with tab1:
    from adapters.visualization.tabs.research_candidates import (
        render as render_candidates,
    )

    render_candidates()
with tab2:
    from adapters.visualization.tabs.risk import render as render_risk

    render_risk()
with tab3:
    from adapters.visualization.tabs.positions import render as render_portfolio

    render_portfolio()
with tab4:
    from adapters.visualization.tabs.stock_analysis import render as render_analysis

    render_analysis()
with tab5:
    from adapters.visualization.tabs.falsification_lab import (
        render as render_falsification,
    )

    render_falsification()
with tab6:
    from adapters.visualization.tabs.methodology import render as render_methodology

    render_methodology()

st.markdown(
    '<div class="ws-footer">Multi-Modal Stock Recommender · Hexagonal Architecture · Built by Tirth Joshi</div>',
    unsafe_allow_html=True,
)
