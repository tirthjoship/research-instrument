"""Performance, Ownership sections."""

from __future__ import annotations

from adapters.visualization.components.cards import criteria_card, verdict_bullet
from adapters.visualization.components.charts import (
    comparison_bars,
    gauge_chart,
    insider_bars,
    ownership_pie,
)
from adapters.visualization.stock_analyzer import AnalysisResult
from adapters.visualization.tabs.stock_analysis.financials_section import (
    _build_margin_items,
)

# ---------------------------------------------------------------------------
# Section 3: Performance
# ---------------------------------------------------------------------------


def _render_performance(result: AnalysisResult) -> None:
    import streamlit as st

    st.divider()
    section = result.performance
    if not section:
        return
    st.markdown("#### 3. Performance")
    st.markdown(
        criteria_card(section.title, section.score, section.max_score, section.summary),
        unsafe_allow_html=True,
    )

    info = result.info
    col_roe, col_margins = st.columns([1, 1])
    with col_roe:
        roe = info.get("returnOnEquity")
        if roe is not None:
            fig = gauge_chart(
                value=float(roe * 100),
                min_v=0,
                max_v=50,
                label="ROE (%)",
                thresholds=(10, 20),
            )
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.caption("ROE data not available")

    with col_margins:
        margin_items = _build_margin_items(info)
        if margin_items:
            fig = comparison_bars(margin_items, value_suffix="%")
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.caption("Margin data not available")

    for status, text in section.verdicts:
        st.markdown(verdict_bullet(status, text), unsafe_allow_html=True)


# ---------------------------------------------------------------------------
# Section 5: Ownership
# ---------------------------------------------------------------------------


def _render_ownership(result: AnalysisResult) -> None:
    import streamlit as st

    st.divider()
    section = result.ownership
    if not section:
        return
    st.markdown("#### 5. Ownership")
    st.markdown(
        criteria_card(section.title, section.score, section.max_score, section.summary),
        unsafe_allow_html=True,
    )

    info = result.info
    col_pie, col_insider = st.columns([1, 1])
    with col_pie:
        inst = float((info.get("heldPercentInstitutions") or 0) * 100)
        insider = float((info.get("heldPercentInsiders") or 0) * 100)
        public = max(0.0, 100.0 - inst - insider)
        if inst > 0 or insider > 0:
            fig = ownership_pie(inst, insider, public)
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.caption("Ownership breakdown not available")

    with col_insider:
        from adapters.visualization.stock_analyzer import aggregate_insider_by_quarter

        if result.insider_transactions:
            quarters = aggregate_insider_by_quarter(result.insider_transactions)
            if quarters:
                fig = insider_bars(quarters)
                st.plotly_chart(fig, use_container_width=True)
            else:
                st.caption("Could not parse insider transaction dates")
        else:
            st.caption("No insider transactions found")

    for status, text in section.verdicts:
        st.markdown(verdict_bullet(status, text), unsafe_allow_html=True)
