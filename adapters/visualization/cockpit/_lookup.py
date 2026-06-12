"""Section 5 — lookup. Ticker or pasted list -> detail drawer / scorecard."""

from __future__ import annotations

import streamlit as st

from adapters.visualization.components.scorecard import render_scorecard
from application.batch_fit_use_case import batch_fit, default_fit_fn, parse_tickers


def render(*, reports_dir: str, summary_path: str) -> None:
    st.subheader("Lookup")
    single = st.text_input("Ticker", key="cp_lookup_ticker", placeholder="e.g. KO")
    if single and st.button("Open detail", key="cp_lookup_open"):
        from adapters.visualization.cockpit.stock_detail import open_stock_detail

        open_stock_detail(single.strip().upper())

    pasted = st.text_area(
        "Or paste a list (comma/newline separated, max 25)", key="cp_lookup_list"
    )
    if pasted and st.button("Check the list", key="cp_lookup_batch"):
        tickers = parse_tickers(pasted)
        if tickers:
            rows = batch_fit(tickers, default_fit_fn)
            render_scorecard(rows)
