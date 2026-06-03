"""Tab 5: Opportunities — Ranked picks with reasoning, watchlist."""

from __future__ import annotations

from typing import Any

import streamlit as st

from adapters.visualization.components.charts import grade_donut
from adapters.visualization.components.formatters import pct
from adapters.visualization.data_loader import load_recommendations, load_watchlist

DB_PATH = "data/recommendations.db"


def render(db_path: str = DB_PATH) -> None:
    """Render the Opportunities tab."""
    st.header("Opportunities")

    recs = load_recommendations(db_path)

    if not recs:
        st.info(
            "No tournament results. Run:\n\n"
            "```\npython -m application.cli run-tournament --market us\n```"
        )
        return

    sorted_recs = sorted(recs, key=lambda r: r.composite_score, reverse=True)

    grade_counts: dict[str, int] = {}
    for r in sorted_recs:
        g = r.grade.value
        grade_counts[g] = grade_counts.get(g, 0) + 1

    col1, col2 = st.columns([2, 1])

    with col1:
        st.subheader("Top Picks")
        _render_picks_table(sorted_recs[:15])

    with col2:
        st.subheader("Grade Distribution")
        fig = grade_donut(grade_counts)
        st.plotly_chart(fig, use_container_width=True)

    st.divider()

    st.subheader("Pick Details")
    for rec in sorted_recs[:15]:
        with st.expander(
            f"{rec.symbol} — {rec.grade.value} (score: {rec.composite_score:.3f})"
        ):
            cols = st.columns(3)
            cols[0].metric("2d", pct(rec.prediction.predicted_return_2d))
            cols[1].metric("5d", pct(rec.prediction.predicted_return_5d))
            cols[2].metric("10d", pct(rec.prediction.predicted_return_10d))
            st.markdown(f"**Reasoning:** {rec.reasoning}")
            if rec.sources:
                st.markdown(f"**Sources:** {', '.join(rec.sources)}")

    st.divider()

    st.subheader("Watchlist")
    watchlist = load_watchlist(db_path)
    if watchlist:
        import pandas as pd

        wdf = pd.DataFrame(watchlist)
        st.dataframe(wdf, use_container_width=True, hide_index=True)
    else:
        st.info(
            "Watchlist empty. Add tickers:\n\n"
            "```\npython -m application.cli add-watchlist NVDA --notes='earnings play'\n```"
        )


def _render_picks_table(recs: list[Any]) -> None:
    """Render top picks as a styled table."""
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
                "Grade": r.grade.value,
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
