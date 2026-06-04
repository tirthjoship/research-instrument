"""Tab 4: Stock Analysis — SWST-grade deep dive for any ticker."""

from __future__ import annotations

import streamlit as st


def render() -> None:
    """Render the Stock Analysis tab — placeholder for Phase 3 implementation."""
    st.markdown("### Stock Analysis")
    st.markdown(
        '<div style="color:#64748B;font-size:14px;margin-bottom:16px;">'
        "Type any S&P 500 or NASDAQ-100 ticker to get a full multi-signal analysis."
        "</div>",
        unsafe_allow_html=True,
    )

    cols = st.columns([4, 1])
    ticker = cols[0].text_input(
        "Ticker", placeholder="NVDA", label_visibility="collapsed"
    )
    analyze = cols[1].button("Run Analysis", type="primary")

    if analyze and ticker:
        st.info(
            f"Full analysis for {ticker.upper()} coming in Phase 3. Foundation components ready."
        )
    elif not ticker:
        st.markdown(
            '<div class="ws-card" style="text-align:center;padding:2rem;">'
            '<div style="font-size:15px;font-weight:500;color:#1A202C;">Enter a ticker above to start</div>'
            '<div style="font-size:13px;color:#64748B;margin-top:4px;">'
            "Get valuation, growth, financial health, sentiment, and conviction analysis"
            "</div></div>",
            unsafe_allow_html=True,
        )
