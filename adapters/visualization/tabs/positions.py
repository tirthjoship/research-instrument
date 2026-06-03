"""Tab 4: My Positions — Holdings, sell signals, add holding form."""

from __future__ import annotations

import streamlit as st

from adapters.visualization.action_runner import run_add_holding, run_monitor_holdings
from adapters.visualization.components.metrics import render_inline_context
from adapters.visualization.data_loader import load_holdings

DB_PATH = "data/recommendations.db"


def render(db_path: str = DB_PATH) -> None:
    """Render the Positions tab."""
    st.markdown("### My Positions")
    render_inline_context(
        st,
        "Track your holdings and monitor for sell signals. "
        "Checks stop-loss (-8%), negative sentiment, and technical breakdown.",
    )

    holdings = load_holdings(db_path)

    if not holdings:
        st.markdown(
            '<div class="dashboard-card card-info">'
            "<strong>No Holdings</strong><br>"
            '<span style="color: #6B7280;">Add your first holding below to start tracking.</span>'
            "</div>",
            unsafe_allow_html=True,
        )
    else:
        # Summary
        total_invested = sum(h.quantity * h.purchase_price for h in holdings)
        cols = st.columns(3)
        cols[0].metric("Positions", str(len(holdings)))
        cols[1].metric("Total Invested", f"${total_invested:,.0f}")
        cols[2].metric("Avg Position", f"${total_invested / len(holdings):,.0f}")

        st.divider()

        # Holdings table
        st.markdown("#### Holdings")
        import pandas as pd

        df = pd.DataFrame(
            [
                {
                    "Symbol": h.symbol,
                    "Quantity": h.quantity,
                    "Purchase Price": f"${h.purchase_price:.2f}",
                    "Est. Value": f"${h.quantity * h.purchase_price:,.0f}",
                    "Date": h.purchase_date,
                    "Notes": h.notes,
                }
                for h in holdings
            ]
        )
        st.dataframe(df, use_container_width=True, hide_index=True)

        st.divider()

        # Sell signals
        st.markdown("#### Sell Signals")
        st.markdown(
            '<p class="section-subtitle">Check your holdings for stop-loss, sentiment, and technical sell triggers.</p>',
            unsafe_allow_html=True,
        )
        if st.button("Check Holdings", type="primary", key="check_holdings"):
            progress = st.progress(0)
            status_text = st.empty()

            def update(pct_val: float, msg: str) -> None:
                progress.progress(pct_val)
                status_text.text(msg)

            signals = run_monitor_holdings(db_path=db_path, progress_callback=update)
            if signals:
                for s in signals:
                    st.markdown(
                        f'<div class="dashboard-card card-sell">'
                        f"<strong>{s.symbol}</strong> — {s.signal_type}<br>"
                        f'<span style="color: #6B7280;">{s.reasoning}</span>'
                        f"</div>",
                        unsafe_allow_html=True,
                    )
            else:
                st.markdown(
                    '<div class="dashboard-card card-buy">'
                    "<strong>All Clear</strong> — No sell signals detected."
                    "</div>",
                    unsafe_allow_html=True,
                )

    st.divider()

    # Add holding form
    st.markdown("#### Add Holding")
    st.markdown(
        '<p class="section-subtitle">Add a new position to your portfolio tracker.</p>',
        unsafe_allow_html=True,
    )
    with st.form("add_holding_form"):
        fcols = st.columns(4)
        symbol = fcols[0].text_input("Symbol", placeholder="NVDA")
        quantity = fcols[1].number_input(
            "Quantity", min_value=0.01, value=10.0, step=1.0
        )
        price = fcols[2].number_input(
            "Price ($)", min_value=0.01, value=100.0, step=1.0
        )
        notes = fcols[3].text_input("Notes", placeholder="AI play")
        submitted = st.form_submit_button("Add Holding", type="primary")
        if submitted and symbol:
            run_add_holding(symbol, quantity, price, notes, db_path)
            st.success(f"Added {symbol.upper()} x{quantity} @ ${price:.2f}")
            st.rerun()
