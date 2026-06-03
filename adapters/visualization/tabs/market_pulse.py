"""Tab 6: Market Pulse — Events, sector momentum, supply chain cascades."""

from __future__ import annotations

import streamlit as st

from adapters.visualization.components.charts import decay_curve
from adapters.visualization.components.metrics import render_info_section
from adapters.visualization.data_loader import load_supply_chains

SUPPLY_CHAIN_PATH = "config/relationships/supply_chain.yaml"


def render(supply_chain_path: str = SUPPLY_CHAIN_PATH) -> None:
    """Render the Market Pulse tab."""
    render_info_section(
        st,
        "Market Pulse",
        "Macro context — events, sector momentum, and supply chain cascades.",
        "This tab shows market-wide signals that affect your ticker universe. "
        "Supply chain cascades show when leader stocks move and followers haven't "
        "reacted yet — a potential opportunity window. Event decay shows how long "
        "news events typically impact prices.",
    )

    # Supply chain cascades (always available from YAML)
    st.markdown("#### Supply Chain Cascades")
    st.markdown(
        '<p class="section-subtitle">When leaders move >3%, followers often follow within 1-3 days.</p>',
        unsafe_allow_html=True,
    )
    with st.expander("ℹ️ Learn more"):
        st.markdown(
            "Supply chain relationships are configured in YAML with 14 groups covering "
            "semiconductors, big tech, energy, pharma, space/defense, retail, AI, cloud, "
            "financials, and housing. Auto-discovered via correlation analysis + manual overrides."
        )

    chains = load_supply_chains(supply_chain_path)

    if chains:
        relationships = chains.get("relationships", [])
        for rel in relationships:
            group_name = rel.get("group", "unknown").replace("_", " ").title()
            lag = rel.get("typical_lag_days", "?")
            inverse = rel.get("inverse", False)
            corr_type = "Inverse" if inverse else "Positive"
            notes = rel.get("notes", "")

            with st.expander(f"{group_name} — {corr_type} · {lag}d lag"):
                leaders = rel.get("leaders", [])
                followers = rel.get("followers", [])

                lcols = st.columns(2)
                with lcols[0]:
                    st.markdown("**Leaders**")
                    for t in leaders:
                        st.markdown(
                            f'<span style="background: #E3F2FD; padding: 2px 8px; '
                            f'border-radius: 4px; margin-right: 4px; font-size: 13px;">{t}</span>',
                            unsafe_allow_html=True,
                        )
                with lcols[1]:
                    st.markdown("**Followers**")
                    for t in followers:
                        st.markdown(
                            f'<span style="background: #FFF3E0; padding: 2px 8px; '
                            f'border-radius: 4px; margin-right: 4px; font-size: 13px;">{t}</span>',
                            unsafe_allow_html=True,
                        )
                if notes:
                    st.caption(notes)
    else:
        st.info("No supply chain config found.")

    st.divider()

    # Event impact decay
    st.markdown("#### Event Impact Decay")
    st.markdown(
        '<p class="section-subtitle">How quickly do news events lose their market impact?</p>',
        unsafe_allow_html=True,
    )
    with st.expander("ℹ️ Learn more"):
        st.markdown(
            "Events decay exponentially: `impact(t) = magnitude × 0.5^(t/half_life)`. "
            "A half-life of 5 days means the impact is halved every 5 days. "
            "Use the sliders to explore different scenarios."
        )
    col1, col2 = st.columns(2)
    magnitude = col1.slider("Impact Magnitude", 0.01, 0.10, 0.05, step=0.01)
    half_life = col2.slider("Half-Life (days)", 1.0, 14.0, 5.0, step=0.5)
    fig = decay_curve(magnitude, half_life)
    st.plotly_chart(fig, use_container_width=True)
