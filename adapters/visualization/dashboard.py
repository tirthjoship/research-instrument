"""Dashboard entry point — two-surface cockpit (Cockpit | Showcase)."""

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

tab_cockpit, tab_showcase = st.tabs(["Cockpit", "Showcase"])

with tab_cockpit:
    from adapters.visualization.cockpit.cockpit import render as render_cockpit

    render_cockpit()
with tab_showcase:
    # Methodology / falsification story — intact until the A2 showcase ships.
    from adapters.visualization.tabs.trust import render as render_trust

    render_trust()

st.markdown(
    '<div class="ws-footer">Multi-Modal Stock Recommender · Hexagonal Architecture · Built by Tirth Joshi</div>',
    unsafe_allow_html=True,
)
