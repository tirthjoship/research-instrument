"""Tab 2: Watchlist — Pinned tickers + add/remove."""

from __future__ import annotations

import streamlit as st

from adapters.visualization.data_loader import load_watchlist

DB_PATH = "data/recommendations.db"


def render(db_path: str = DB_PATH) -> None:
    st.markdown("### Watchlist")
    st.markdown(
        "<div style=\"color:#64748B;font-size:14px;margin-bottom:16px;\">Tickers you're watching. Pin from Today's Opportunities or add manually below.</div>",
        unsafe_allow_html=True,
    )

    watchlist = load_watchlist(db_path)

    if not watchlist:
        st.markdown(
            '<div class="ws-card" style="text-align:center;padding:2rem;">'
            '<div style="font-size:15px;font-weight:500;color:#1A202C;">Your watchlist is empty</div>'
            '<div style="font-size:13px;color:#64748B;margin-top:4px;">Pin tickers from Today\'s Opportunities to track them here.</div></div>',
            unsafe_allow_html=True,
        )
    else:
        import pandas as pd

        df = pd.DataFrame(watchlist)
        st.dataframe(df, use_container_width=True, hide_index=True)

    st.divider()
    with st.form("add_watchlist_form", clear_on_submit=True):
        cols = st.columns([3, 5, 2])
        ticker = cols[0].text_input("Symbol", placeholder="TSLA")
        notes = cols[1].text_input("Notes", placeholder="Earnings play")
        submitted = cols[2].form_submit_button("Add")
        if submitted and ticker:
            from adapters.visualization.action_runner import run_add_watchlist

            run_add_watchlist(ticker.upper(), notes, db_path=db_path)
            st.rerun()
