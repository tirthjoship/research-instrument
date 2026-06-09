"""Weekly Brief tab — renders the most recent generated brief markdown."""

from __future__ import annotations

import streamlit as st

from adapters.visualization.data_loader import load_weekly_brief

_BRIEF_PATH = "data/personal/weekly_brief.md"


def render(path: str = _BRIEF_PATH) -> None:
    """Render the unified weekly brief (read-only viewer)."""
    st.subheader("Weekly Brief")
    md = load_weekly_brief(path)
    if md is None:
        st.info(
            "No brief generated yet. Run `python -m application.cli weekly-brief` "
            "to generate it (stays on your machine)."
        )
        return
    st.markdown(md)
    st.caption(
        "Evidence-ranked, not validated where the screen label is RESEARCH_ONLY. "
        "Phase B adds no predictive claim."
    )
