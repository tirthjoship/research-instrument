"""Tab 5: Opportunities — Ranked picks with reasoning, watchlist."""

from __future__ import annotations

from typing import Any

import streamlit as st

from adapters.visualization.action_runner import run_add_watchlist
from adapters.visualization.components.charts import grade_donut
from adapters.visualization.components.formatters import grade_display_name, pct
from adapters.visualization.components.metrics import render_info_section
from adapters.visualization.data_loader import load_recommendations, load_watchlist

DB_PATH = "data/recommendations.db"


def render(db_path: str = DB_PATH) -> None:
    """Render the Opportunities tab."""
    render_info_section(
        st,
        "Opportunities",
        "Latest tournament picks ranked by composite score — what to consider buying.",
        "The tournament scores all tickers in the universe using the 5-layer "
        "feature architecture and ranks them by composite score. Grade distribution "
        "shows the model's current market view. Click any pick for detailed reasoning.",
    )

    recs = load_recommendations(db_path)

    if not recs:
        st.markdown(
            '<div class="dashboard-card card-info">'
            "<strong>No Tournament Results</strong><br>"
            '<span style="color: #6B7280;">Run a tournament to generate ranked picks.</span>'
            "</div>",
            unsafe_allow_html=True,
        )
        return

    sorted_recs = sorted(recs, key=lambda r: r.composite_score, reverse=True)

    # Grade counts with display names
    grade_counts: dict[str, int] = {}
    for r in sorted_recs:
        display = grade_display_name(r.grade.value)
        grade_counts[display] = grade_counts.get(display, 0) + 1

    col1, col2 = st.columns([2, 1])

    with col1:
        st.markdown("#### Top Picks")
        _render_picks_table(sorted_recs[:15])

    with col2:
        st.markdown("#### Grade Distribution")
        with st.expander("ℹ️ Learn more"):
            st.markdown(
                "Grade distribution shows the model's current market view. "
                "Mostly Holds = limited opportunities. Mostly Buys = model is bullish."
            )
        fig = grade_donut(grade_counts)
        st.plotly_chart(fig, use_container_width=True)

    st.divider()

    st.markdown("#### Pick Details")
    st.markdown(
        '<p class="section-subtitle">Click any pick to see full reasoning and multi-horizon predictions.</p>',
        unsafe_allow_html=True,
    )
    for rec in sorted_recs[:15]:
        display = grade_display_name(rec.grade.value)
        with st.expander(
            f"{rec.symbol} — {display} (score: {rec.composite_score:.3f})"
        ):
            cols = st.columns(3)
            cols[0].metric("2d Return", pct(rec.prediction.predicted_return_2d))
            cols[1].metric("5d Return", pct(rec.prediction.predicted_return_5d))
            cols[2].metric("10d Return", pct(rec.prediction.predicted_return_10d))
            st.markdown(f"**Reasoning:** {rec.reasoning}")
            if rec.sources:
                st.markdown(f"**Sources:** {', '.join(rec.sources)}")

    st.divider()

    # Watchlist
    st.markdown("#### Watchlist")
    st.markdown(
        '<p class="section-subtitle">Track tickers you\'re interested in but not yet holding.</p>',
        unsafe_allow_html=True,
    )
    watchlist = load_watchlist(db_path)
    if watchlist:
        import pandas as pd

        wdf = pd.DataFrame(watchlist)
        wdf.columns = pd.Index(["Symbol", "Added", "Notes"])
        st.dataframe(wdf, use_container_width=True, hide_index=True)

    # Add to watchlist form
    with st.form("add_watchlist_form"):
        wcols = st.columns([2, 3, 1])
        w_symbol = wcols[0].text_input("Symbol", placeholder="TSLA", key="wl_sym")
        w_notes = wcols[1].text_input(
            "Notes", placeholder="earnings play", key="wl_notes"
        )
        w_submit = wcols[2].form_submit_button("Add")
        if w_submit and w_symbol:
            run_add_watchlist(w_symbol, w_notes, db_path)
            st.success(f"Added {w_symbol.upper()} to watchlist")
            st.rerun()


def _render_picks_table(recs: list[Any]) -> None:
    """Render top picks table with grade display names."""
    import pandas as pd

    rows = []
    for i, r in enumerate(recs, 1):
        signals = r.horizon_signals or {}
        bullish_count = sum(1 for v in signals.values() if v == "bullish")
        total = len(signals) if signals else 0
        rows.append(
            {
                "Rank": i,
                "Symbol": r.symbol,
                "Grade": grade_display_name(r.grade.value),
                "Score": f"{r.composite_score:.3f}",
                "Conf": (
                    f"{r.prediction.confidence_5d:.0%}"
                    if r.prediction.confidence_5d
                    else "—"
                ),
                "5d Pred": pct(r.prediction.predicted_return_5d),
                "Layers": f"{bullish_count}/{total}" if total else "—",
            }
        )
    df = pd.DataFrame(rows)
    st.dataframe(df, use_container_width=True, hide_index=True)
