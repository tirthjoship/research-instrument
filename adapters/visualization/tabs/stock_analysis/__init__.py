"""Stock analysis tab package."""

from adapters.visualization.tabs.stock_analysis.corroboration_section import (  # noqa: F401
    render_corroboration_section,
)

# Populated by Task 4 (compose.py). Stub satisfies dashboard.py import during transition.
_SECTION_LABELS: list[str] = []


def render() -> None:  # pragma: no cover
    """Entry point — implemented in compose.py (Task 4)."""
    import streamlit as st

    st.info("Stock Analysis tab is being upgraded — check back shortly.")
