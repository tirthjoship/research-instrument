# adapters/visualization/components/expandable_row.py
"""Shared merged-row-plus-chevron toggle for Needs Review / Holding Steady lists.

st.expander cannot take rich HTML (badges, RAG squares, sparkline) as its
label — that constraint is why a row and its "expand for full evidence"
control used to render as two separate elements, each repeating the ticker
and verdict text. This renders the row's own HTML next to a small toggle
button inside one bordered container, so the whole thing reads as one
element and the click target never repeats the row's own content.
"""

from __future__ import annotations

from typing import Callable

import streamlit as st


def render_toggle_row(
    *,
    row_html: str,
    session_key: str,
    detail: Callable[[], None],
) -> None:
    """Render row_html with a trailing chevron toggle; call detail() beneath
    the row when open.

    session_key: a unique per-row st.session_state boolean key (e.g.
    f"nr_open_{ticker}") tracking whether this row is expanded. Callers own
    key uniqueness — this function only reads/writes the given key.
    detail: zero-arg callback rendering the expanded content, already bound
    to this row's data by the caller. Called only when open, so evidence
    fetches inside it stay lazy.
    """
    is_open = bool(st.session_state.get(session_key, False))
    with st.container(border=True):
        cols = st.columns([0.95, 0.05])
        with cols[0]:
            st.markdown(row_html, unsafe_allow_html=True)
        with cols[1]:
            if st.button(
                "⌃" if is_open else "⌄",
                key=f"{session_key}_btn",
                use_container_width=True,
            ):
                st.session_state[session_key] = not is_open
                st.rerun()
        if is_open:
            detail()
