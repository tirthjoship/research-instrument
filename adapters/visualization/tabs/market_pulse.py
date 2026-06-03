"""Tab 6: Market Pulse — Active events, sector momentum, supply chain cascades."""

from __future__ import annotations

import streamlit as st

from adapters.visualization.components.charts import decay_curve
from adapters.visualization.data_loader import load_supply_chains

SUPPLY_CHAIN_PATH = "config/relationships/supply_chain.yaml"


def render(supply_chain_path: str = SUPPLY_CHAIN_PATH) -> None:
    """Render the Market Pulse tab."""
    st.header("Market Pulse")

    st.subheader("Active Events")
    st.info(
        "Run event classification to populate:\n\n"
        "```\npython -m application.cli daily-scan --market us\n```"
    )

    st.divider()

    st.subheader("Sector Momentum")
    st.info(
        "Sector momentum heatmap populates after running tournament "
        "with market data. Requires sector ETF data from us.yaml config."
    )

    st.divider()

    st.subheader("Supply Chain Cascades")
    chains = load_supply_chains(supply_chain_path)

    if chains:
        relationships = chains.get("relationships", [])
        for rel in relationships:
            group_name = rel.get("group", "unknown")
            with st.expander(f"🔗 {group_name}"):
                leaders = rel.get("leaders", [])
                followers = rel.get("followers", [])
                lag = rel.get("typical_lag_days", "?")
                inverse = rel.get("inverse", False)
                if leaders:
                    st.markdown(f"**Leaders:** {', '.join(leaders)}")
                if followers:
                    st.markdown(f"**Followers:** {', '.join(followers)}")
                st.caption(
                    f"Lag: {lag}d | {'Inverse' if inverse else 'Positive'} correlation | "
                    f"When leaders move >3%, check if followers haven't reacted yet."
                )
    else:
        st.info("No supply chain config found.")

    st.divider()

    st.subheader("Event Impact Decay (Example)")
    col1, col2 = st.columns(2)
    magnitude = col1.slider("Impact Magnitude", 0.01, 0.10, 0.05, step=0.01)
    half_life = col2.slider("Half-Life (days)", 1.0, 14.0, 5.0, step=0.5)
    fig = decay_curve(magnitude, half_life)
    st.plotly_chart(fig, use_container_width=True)
