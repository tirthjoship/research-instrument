"""Tab 4: My Positions — Holdings P&L, sell signals, risk concentration."""

from __future__ import annotations

import streamlit as st

from adapters.visualization.data_loader import load_holdings

DB_PATH = "data/recommendations.db"


def render(db_path: str = DB_PATH) -> None:
    """Render the Positions tab."""
    st.header("My Positions")

    holdings = load_holdings(db_path)

    if not holdings:
        st.info(
            "No holdings tracked. Add with:\n\n"
            "```\npython -m application.cli add-holding NVDA 10 --price=950\n```"
        )
        return

    cols = st.columns(3)
    cols[0].metric("Positions", str(len(holdings)))
    at_risk = 0
    cols[1].metric("At Risk", str(at_risk))
    cols[2].metric("Total Value", "Run monitor-holdings for live data")

    st.divider()

    st.subheader("Holdings")
    import pandas as pd

    df = pd.DataFrame(
        [
            {
                "Symbol": h.symbol,
                "Quantity": h.quantity,
                "Purchase Price": f"${h.purchase_price:.2f}",
                "Purchase Date": h.purchase_date,
                "Notes": h.notes,
            }
            for h in holdings
        ]
    )
    st.dataframe(df, use_container_width=True, hide_index=True)

    st.divider()

    st.subheader("Sell Signals")
    st.info(
        "Run monitor-holdings for live sell signal detection:\n\n"
        "```\npython -m application.cli monitor-holdings\n```"
    )
