"""TDD: adapters.visualization.book_context.resolve_ui_book_context().

Single source of truth for which book + brief/screen artifacts the Streamlit UI
shows. Priority: session-uploaded book (explicitly flagged non-sample) -> bundled
sample book. Must never read data/personal/* for UI resolution.
"""

from __future__ import annotations

import streamlit as st

from application.holdings_reader import Holding


def test_resolve_defaults_to_sample_when_session_empty(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    from adapters.visualization import book_context

    monkeypatch.setattr(st, "session_state", {}, raising=False)

    ctx = book_context.resolve_ui_book_context()

    assert ctx.is_sample is True
    assert {h.ticker for h in ctx.book} == {
        "AAPL",
        "MSFT",
        "NVDA",
        "GOOGL",
        "AMZN",
        "TSLA",
        "META",
        "JPM",
        "V",
        "BRK-B",
    }
    assert ctx.brief_path == book_context.SAMPLE_BRIEF_PATH
    assert ctx.reports_dir == book_context.SAMPLE_REPORTS_DIR


def test_resolve_uses_session_book_when_flagged_non_sample(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    from adapters.visualization import book_context

    session_book = [Holding("COST", 5.0, 900.0, "TFSA")]
    monkeypatch.setattr(
        st,
        "session_state",
        {
            book_context.SESSION_BOOK_KEY: session_book,
            book_context.SESSION_IS_SAMPLE_KEY: False,
            book_context.SESSION_BRIEF_PATH_KEY: "/tmp/session/brief_summary.json",
            book_context.SESSION_REPORTS_DIR_KEY: "/tmp/session",
        },
        raising=False,
    )

    ctx = book_context.resolve_ui_book_context()

    assert ctx.is_sample is False
    assert ctx.book is session_book
    assert ctx.brief_path == "/tmp/session/brief_summary.json"
    assert ctx.reports_dir == "/tmp/session"


def test_resolve_ignores_session_book_when_still_flagged_sample(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    """_handle_onboarding stores the sample book in session_state too — the
    resolver must still route to the committed sample artifacts, not a stray
    session brief path, whenever is_sample_book is True."""
    from adapters.visualization import book_context

    monkeypatch.setattr(
        st,
        "session_state",
        {
            book_context.SESSION_BOOK_KEY: [Holding("AAPL", 10.0, 1800.0, "TFSA")],
            book_context.SESSION_IS_SAMPLE_KEY: True,
            book_context.SESSION_BRIEF_PATH_KEY: "/tmp/should-not-be-used.json",
        },
        raising=False,
    )

    ctx = book_context.resolve_ui_book_context()

    assert ctx.is_sample is True
    assert ctx.brief_path == book_context.SAMPLE_BRIEF_PATH


def test_resolve_treats_empty_session_book_as_sample(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    """An empty list (e.g. a stale/cleared session key) must not count as a
    real session book — falls back to sample rather than showing zero holdings."""
    from adapters.visualization import book_context

    monkeypatch.setattr(
        st,
        "session_state",
        {book_context.SESSION_BOOK_KEY: [], book_context.SESSION_IS_SAMPLE_KEY: False},
        raising=False,
    )

    ctx = book_context.resolve_ui_book_context()

    assert ctx.is_sample is True
    assert len(ctx.book) == 10
