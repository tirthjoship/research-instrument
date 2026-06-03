"""Tab 5: Opportunities — Top picks as cards, ranked table, watchlist."""

from __future__ import annotations

from typing import Any

import streamlit as st

from adapters.visualization.action_runner import run_add_watchlist, run_tournament
from adapters.visualization.components.charts import grade_donut
from adapters.visualization.components.formatters import (
    grade_display_name,
    pct,
    signal_pill_html,
)
from adapters.visualization.components.metrics import (
    render_inline_context,
    render_pick_card,
)
from adapters.visualization.components.verdicts import pick_verdict
from adapters.visualization.data_loader import load_recommendations, load_watchlist

DB_PATH = "data/recommendations.db"


def render(db_path: str = DB_PATH) -> None:
    """Render the Opportunities tab."""
    st.markdown("### Opportunities")
    render_inline_context(
        st,
        "Tournament picks ranked by composite score. "
        "Top 5 shown as detailed cards, rest in compact table.",
    )

    if st.button("Run Tournament", type="primary", key="run_tournament"):
        progress = st.progress(0)
        status_text = st.empty()

        def update(pct_val: float, msg: str) -> None:
            progress.progress(pct_val)
            status_text.text(msg)

        try:
            run_tournament(db_path=db_path, progress_callback=update)
            st.success("Tournament complete")
            st.rerun()
        except Exception as e:
            st.error(f"Tournament failed: {e}")

    recs = load_recommendations(db_path)

    if not recs:
        st.markdown(
            '<div class="dashboard-card card-info">'
            "<strong>No tournament results</strong><br>"
            '<span style="color: #6B7280;">Click "Run Tournament" above to generate ranked picks.</span>'
            "</div>",
            unsafe_allow_html=True,
        )
        return

    sorted_recs = sorted(recs, key=lambda r: r.composite_score, reverse=True)

    grade_counts: dict[str, int] = {}
    for r in sorted_recs:
        display = grade_display_name(r.grade.value)
        grade_counts[display] = grade_counts.get(display, 0) + 1

    # Top 5 as cards
    st.markdown("#### Top 5 Picks")
    for i, rec in enumerate(sorted_recs[:5], 1):
        signals = rec.horizon_signals or {}
        bullish = sum(1 for v in signals.values() if v == "bullish")
        total = len(signals)

        layer_dots_parts = []
        for horizon, direction in signals.items():
            pill = signal_pill_html(direction)
            layer_dots_parts.append(f"{horizon}: {pill}")
        layer_dots = " · ".join(layer_dots_parts) if layer_dots_parts else "—"

        verdict = pick_verdict(
            grade=rec.grade.value,
            n_bullish=bullish,
            n_total=total,
            reasoning=rec.reasoning[:80] if rec.reasoning else "—",
        )

        sources = ", ".join(rec.sources) if rec.sources else "yfinance"

        render_pick_card(
            st,
            rank=i,
            symbol=rec.symbol,
            grade=rec.grade.value,
            verdict=verdict,
            predicted_5d=pct(rec.prediction.predicted_return_5d),
            confidence=rec.prediction.confidence_5d,
            layer_dots=layer_dots,
            sources=sources,
        )

    st.divider()

    col1, col2 = st.columns([2, 1])

    with col1:
        st.markdown("#### Picks #6-15")
        if len(sorted_recs) > 5:
            _render_compact_table(sorted_recs[5:15])
        else:
            st.caption("Fewer than 6 picks available")

    with col2:
        st.markdown("#### Grade Distribution")
        render_inline_context(st, "Model's current market view")
        fig = grade_donut(grade_counts)
        st.plotly_chart(fig, use_container_width=True)

    st.divider()

    st.markdown("#### Watchlist")
    render_inline_context(st, "Tickers you're watching but not yet holding.")
    watchlist = load_watchlist(db_path)
    if watchlist:
        import pandas as pd

        wdf = pd.DataFrame(watchlist)
        wdf.columns = pd.Index(["Symbol", "Added", "Notes"])
        st.dataframe(wdf, use_container_width=True, hide_index=True)

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


def _render_compact_table(recs: list[Any]) -> None:
    """Compact table for picks #6-15."""
    import pandas as pd

    rows = []
    for i, r in enumerate(recs, 6):
        rows.append(
            {
                "Rank": i,
                "Symbol": r.symbol,
                "Grade": grade_display_name(r.grade.value),
                "Score": f"{r.composite_score:.3f}",
                "5d Pred": pct(r.prediction.predicted_return_5d),
            }
        )
    df = pd.DataFrame(rows)
    st.dataframe(df, use_container_width=True, hide_index=True)
