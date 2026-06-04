"""Dashboard entry point — 5-tab router."""

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

tab1, tab2, tab3, tab4, tab5 = st.tabs(
    [
        "Today's Opportunities",
        "Watchlist",
        "My Portfolio",
        "How It Works",
        "Market Context",
    ]
)

with tab1:
    from adapters.visualization.tabs.command_center import render as render_opps

    render_opps()
with tab2:
    from adapters.visualization.tabs.watchlist import render as render_watch

    render_watch()
with tab3:
    from adapters.visualization.tabs.positions import render as render_portfolio

    render_portfolio()
with tab4:
    from adapters.visualization.tabs.model_confidence import render as render_hiw

    render_hiw()
with tab5:
    from adapters.visualization.tabs.market_pulse import render as render_market

    render_market()

st.markdown(
    '<div class="ws-footer">Multi-Modal Stock Recommender · Built by Tirth Joshi</div>',
    unsafe_allow_html=True,
)
