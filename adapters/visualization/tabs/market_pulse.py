"""Tab 6: Market Pulse — Data sources, supply chains, event decay."""

from __future__ import annotations

import streamlit as st

from adapters.visualization.components.charts import decay_curve
from adapters.visualization.components.metrics import render_inline_context
from adapters.visualization.data_loader import load_supply_chains

SUPPLY_CHAIN_PATH = "config/relationships/supply_chain.yaml"


def render(supply_chain_path: str = SUPPLY_CHAIN_PATH) -> None:
    """Render the Market Pulse tab."""
    st.markdown("### Market Context")
    render_inline_context(
        st,
        "Background intelligence — data sources, supply chain relationships, "
        "and event impact modeling.",
    )

    _render_data_sources()
    st.divider()
    _render_supply_chains(supply_chain_path)
    st.divider()
    _render_event_decay()


def _render_data_sources() -> None:
    """Show data pipeline status as a styled grid."""
    st.markdown("#### Data Pipeline")
    render_inline_context(st, "What data sources are connected and when they last ran.")

    sources = [
        ("RSS Feeds", True, "15 feeds configured"),
        ("Google Trends", True, "350 tickers tracked"),
        ("StockTwits", True, "Live sentiment"),
        ("GDELT", False, "Available in future phase"),
        ("Fundamental", True, "Via yfinance (real-time)"),
        ("Cross-Asset", True, "Correlation matrix (daily)"),
        ("Event-Causal", True, "Gemini classifier (10 categories)"),
        ("SEC EDGAR", True, "13D activist filings + Form 4 insider trades"),
    ]

    cards_html = ""
    for name, active, detail in sources:
        dot_color = "#22C55E" if active else "#EF4444"
        dot_html = (
            f'<span style="display:inline-block; width:8px; height:8px; '
            f"border-radius:50%; background:{dot_color}; "
            f'margin-right:6px; flex-shrink:0; margin-top:3px;"></span>'
        )
        cards_html += (
            f'<div class="ws-card" style="padding:12px 14px;">'
            f'<div style="display:flex; align-items:flex-start; margin-bottom:4px;">'
            f"{dot_html}"
            f'<strong style="font-size:13px;">{name}</strong>'
            f"</div>"
            f'<span style="color:#6B7280; font-size:12px;">{detail}</span>'
            f"</div>"
        )

    grid_html = (
        f'<div style="display:grid; grid-template-columns: repeat(auto-fill, minmax(220px, 1fr)); '
        f'gap:12px; margin-top:8px;">'
        f"{cards_html}"
        f"</div>"
    )
    st.markdown(grid_html, unsafe_allow_html=True)


def _render_supply_chains(supply_chain_path: str) -> None:
    """Show supply chain cascades — all groups expanded."""
    st.markdown("#### Supply Chain Cascades")
    render_inline_context(
        st,
        "When leader stocks move >3%, follower stocks often follow within 1-3 days.",
    )

    chains = load_supply_chains(supply_chain_path)

    if not chains:
        st.caption("No supply chain config found.")
        return

    relationships = chains.get("relationships", [])
    for rel in relationships:
        group_name = rel.get("group", "unknown").replace("_", " ").title()
        lag = rel.get("typical_lag_days", "?")
        inverse = rel.get("inverse", False)
        corr_type = "Inverse" if inverse else "Positive"
        notes = rel.get("notes", "")

        st.markdown(
            f'<div class="ws-card">'
            f"<strong>{group_name}</strong> — {corr_type} · {lag}d lag",
            unsafe_allow_html=True,
        )

        leaders = rel.get("leaders", [])
        followers = rel.get("followers", [])

        lcols = st.columns(2)
        with lcols[0]:
            leader_tags = " ".join(
                f'<span style="background: #DBEAFE; padding: 2px 8px; '
                f"border-radius: 4px; margin: 2px; font-size: 13px; "
                f'display: inline-block;">{t}</span>'
                for t in leaders
            )
            st.markdown(f"**Leaders** {leader_tags}", unsafe_allow_html=True)
        with lcols[1]:
            follower_tags = " ".join(
                f'<span style="background: #FFEDD5; padding: 2px 8px; '
                f"border-radius: 4px; margin: 2px; font-size: 13px; "
                f'display: inline-block;">{t}</span>'
                for t in followers
            )
            st.markdown(f"**Followers** {follower_tags}", unsafe_allow_html=True)

        if notes:
            st.markdown(
                f'<span style="color: #9CA3AF; font-size: 12px;">{notes}</span>'
                f"</div>",
                unsafe_allow_html=True,
            )
        else:
            st.markdown("</div>", unsafe_allow_html=True)


def _render_event_decay() -> None:
    """Event impact decay interactive visualization."""
    st.markdown("#### Event Impact Decay")
    render_inline_context(
        st,
        "How quickly news events lose market impact. "
        "A 5% earnings surprise loses half its effect in ~5 days.",
    )

    col1, col2 = st.columns(2)
    magnitude = col1.slider("Impact Magnitude", 0.01, 0.10, 0.05, step=0.01)
    half_life = col2.slider("Half-Life (days)", 1.0, 14.0, 5.0, step=0.5)

    remaining = magnitude * (0.5 ** (5 / half_life))
    render_inline_context(
        st,
        f"After 5 days, a {magnitude:.0%} impact decays to {remaining:.2%} remaining.",
    )

    fig = decay_curve(magnitude, half_life)
    st.plotly_chart(fig, use_container_width=True)
