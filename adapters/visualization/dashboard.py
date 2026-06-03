"""Dashboard entry point — tab router and page config.

Run: streamlit run adapters/visualization/dashboard.py
"""

from __future__ import annotations

import streamlit as st

st.set_page_config(
    page_title="Stock Recommender Dashboard",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# Inject global CSS before any content
from adapters.visualization.components.styles import inject_global_css  # noqa: E402

inject_global_css()

# Branding header
st.markdown(
    '<h1 style="margin-bottom: 0;">📈 Multi-Modal Stock Recommender</h1>'
    '<p style="color: #6B7280; font-size: 15px; margin-top: 4px;">'
    "Decision dashboard — 5 signal layers · 101 features · hexagonal architecture"
    "</p>",
    unsafe_allow_html=True,
)

# Tab router
tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs(
    [
        "🎯 Command Center",
        "📊 Model Confidence",
        "🔍 Signal Breakdown",
        "💼 My Positions",
        "🚀 Opportunities",
        "🌍 Market Pulse",
    ]
)

with tab1:
    from adapters.visualization.tabs.command_center import render as render_cc

    render_cc()

with tab2:
    from adapters.visualization.tabs.model_confidence import render as render_mc

    render_mc()

with tab3:
    from adapters.visualization.tabs.signal_breakdown import render as render_sb

    render_sb()

with tab4:
    from adapters.visualization.tabs.positions import render as render_pos

    render_pos()

with tab5:
    from adapters.visualization.tabs.opportunities import render as render_opp

    render_opp()

with tab6:
    from adapters.visualization.tabs.market_pulse import render as render_mp

    render_mp()
