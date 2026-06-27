"""Sentiment, Supply Chain sections."""

from __future__ import annotations

from adapters.visualization.components.cards import criteria_card, verdict_bullet
from adapters.visualization.components.charts import cluster_bubble
from adapters.visualization.stock_analyzer import AnalysisResult

# ---------------------------------------------------------------------------
# Section 6: Sentiment
# ---------------------------------------------------------------------------


def _render_sentiment(result: AnalysisResult) -> None:
    import streamlit as st

    st.divider()
    section = result.sentiment
    if not section:
        return
    st.markdown("#### 6. Sentiment")
    st.caption(
        "Descriptive buzz only — predictive value was tested and falsified "
        "(ADR-044: no cross-sectional IC on a clean 430-ticker universe)."
    )
    st.markdown(
        criteria_card(section.title, section.score, section.max_score, section.summary),
        unsafe_allow_html=True,
    )

    buzz = result.buzz_signals
    if buzz:
        # Show summary table of recent buzz
        rows = []
        for b in buzz[:10]:
            rows.append(
                {
                    "Source": getattr(b, "source", "unknown"),
                    "Sentiment": f"{getattr(b, 'sentiment_raw', 0):.2f}",
                    "Mentions": getattr(b, "mention_count", 0),
                    "Date": str(getattr(b, "fetched_at", ""))[:10],
                }
            )
        if rows:
            import pandas as pd

            st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)
    else:
        st.markdown(
            '<div class="ws-card" style="text-align:center;padding:16px;">'
            '<div style="font-size:14px;color:#64748B;">No sentiment signals in database</div>'
            '<div style="font-size:12px;color:#94A3B8;margin-top:4px;">'
            "Run <code>make daily-scan</code> to populate sentiment data"
            "</div></div>",
            unsafe_allow_html=True,
        )

    for status, text in section.verdicts:
        st.markdown(verdict_bullet(status, text), unsafe_allow_html=True)


# ---------------------------------------------------------------------------
# Section 7: Supply Chain
# ---------------------------------------------------------------------------


def _render_supply_chain(result: AnalysisResult) -> None:
    import streamlit as st

    st.divider()
    section = result.supply_chain
    if not section:
        return
    st.markdown("#### 7. Supply Chain")
    st.markdown(
        criteria_card(section.title, section.score, section.max_score, section.summary),
        unsafe_allow_html=True,
    )

    sc_group = result.supply_chain_group
    if sc_group:
        # Build bubble chart data from peers + self
        all_tickers_in_group = sc_group.get("leaders", []) + sc_group.get(
            "followers", []
        )
        # Use peer_data for market caps; fill in self
        peer_lookup = {p["ticker"]: p for p in result.peer_data}
        bubble_data = []
        for t in all_tickers_in_group[:10]:
            pd_info = peer_lookup.get(t, {})
            mc = float(pd_info.get("market_cap", 0) or 0)
            if t == result.ticker:
                mc = result.market_cap
            role = "leader" if t in sc_group.get("leaders", []) else "follower"
            bubble_data.append(
                {
                    "ticker": t,
                    "market_cap": mc if mc > 0 else 1e9,
                    "change_pct": float(pd_info.get("change_pct", 0) or 0),
                    "role": role,
                }
            )
        if bubble_data:
            group_name = (
                sc_group.get("group", "Supply Chain Group").replace("_", " ").title()
            )
            fig = cluster_bubble(bubble_data, group_name, highlight=result.ticker)
            st.plotly_chart(fig, use_container_width=True)
    else:
        st.markdown(
            '<div class="ws-card" style="text-align:center;padding:16px;">'
            '<div style="font-size:14px;color:#64748B;">Not in a tracked supply chain group</div>'
            '<div style="font-size:12px;color:#94A3B8;margin-top:4px;">'
            "Cross-asset supply chain signals are not available for this ticker"
            "</div></div>",
            unsafe_allow_html=True,
        )

    for status, text in section.verdicts:
        st.markdown(verdict_bullet(status, text), unsafe_allow_html=True)
