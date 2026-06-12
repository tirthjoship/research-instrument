"""Research Candidates tab — factual evidence ranking. RESEARCH_ONLY, no buy language."""

from __future__ import annotations

import streamlit as st

from adapters.visualization.components.formatters import status_pill_html
from adapters.visualization.data_loader import load_latest_screen, staleness_days

_TOP_N = 15

_DISCLAIMER = (
    "Ranked by **current factual evidence** (valuation · quality · health) — "
    "**NOT predicted returns**. Prediction was tested 2006–2024 and falsified "
    "(see the Falsification Lab tab)."
)


def render(reports_dir: str = "data/reports") -> None:
    st.subheader("Research Candidates")
    st.markdown(
        '<div class="ws-card" style="padding:10px 16px;margin-bottom:12px;">'
        f"{_DISCLAIMER}"
        "</div>",
        unsafe_allow_html=True,
    )

    screen = load_latest_screen(reports_dir)
    if screen is None:
        st.warning(
            "No screen report found. Run "
            "`python -m application.cli screen-candidates` to generate one."
        )
        return

    days = staleness_days(screen.get("as_of", ""))
    if days is not None and days > 8:
        st.error(f"Screen is {days} days old — re-run `screen-candidates`.")

    if screen.get("abstained"):
        st.markdown(
            '<div class="ws-card" style="padding:12px 16px;margin-bottom:12px;">'
            '<span style="font-weight:700;color:#64748B;">ABSTAINED</span> — '
            "The evidence screen ABSTAINED — no name met the evidence bar. "
            "That is the tool working, not failing."
            "</div>",
            unsafe_allow_html=True,
        )

    candidates = screen.get("candidates", [])[:_TOP_N]
    if not candidates:
        st.caption("No ranked candidates in the latest report.")
        return

    as_of = screen.get("as_of", "?")
    universe_size = screen.get("universe_size", "?")
    first_label = screen.get("candidates", [{}])[0].get("label", "RESEARCH_ONLY")
    st.caption(
        f"Top {len(candidates)} of {universe_size} by factual composite · "
        f"as of {as_of} · label: {first_label}"
    )

    for i, c in enumerate(candidates, start=1):
        factors = c.get("factor_scores", [])
        # percentile is a 0–1 FRACTION in the screen JSON — multiply by 100 for display
        chips = " · ".join(
            f"{f.get('name', '?')} p{f.get('percentile', 0) * 100:.0f}" for f in factors
        )
        ticker = c.get("ticker", "?")
        composite = c.get("composite", 0)
        why = c.get("why", "")
        label = c.get("label", "RESEARCH_ONLY")
        pill = status_pill_html("neutral", label)
        st.markdown(
            f'<div class="ws-card" style="padding:12px 16px;margin-bottom:8px;">'
            f"<strong>{i}. {ticker}</strong> — composite {composite:.2f} {pill}<br>"
            f'<span style="color:#6B7280;font-size:13px;">{chips}</span><br>'
            f"<em>{why}</em> — research it in the Stock Analysis tab."
            "</div>",
            unsafe_allow_html=True,
        )
