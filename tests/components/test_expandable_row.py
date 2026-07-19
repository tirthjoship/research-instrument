# tests/components/test_expandable_row.py
from __future__ import annotations

from adapters.visualization.components.expandable_row import render_toggle_row


def test_render_toggle_row_closed_by_default_does_not_call_detail(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    """When the session_key isn't set yet, the row renders but detail() must
    not be called — expansion is opt-in, not eager."""
    import streamlit as st

    st.session_state.clear()
    calls: list[str] = []
    render_toggle_row(
        row_html="<div>AAPL row</div>",
        session_key="nr_open_AAPL",
        detail=lambda: calls.append("rendered"),
    )
    assert calls == []


def test_render_toggle_row_open_calls_detail(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    """When session_state[session_key] is already True, detail() must render
    beneath the row on this same pass (no extra click needed to see it)."""
    import streamlit as st

    st.session_state.clear()
    st.session_state["nr_open_AAPL"] = True
    calls: list[str] = []
    render_toggle_row(
        row_html="<div>AAPL row</div>",
        session_key="nr_open_AAPL",
        detail=lambda: calls.append("rendered"),
    )
    assert calls == ["rendered"]
