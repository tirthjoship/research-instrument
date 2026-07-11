"""Single source of truth for which book + brief/screen artifacts the Streamlit
UI shows: a session-uploaded book, or the bundled sample book.

Never reads ``data/personal/*`` — that stays the CLI dogfood path, outside the
public UI (see docs/superpowers/specs/2026-07-11-public-sample-book-design.md).
"""

from __future__ import annotations

from dataclasses import dataclass

import streamlit as st

from application.holdings_reader import Holding
from application.sample_book import load_sample_book

SAMPLE_BRIEF_PATH = "data/sample/brief_summary.json"
SAMPLE_REPORTS_DIR = "data/sample"

SESSION_BOOK_KEY = "book"
SESSION_IS_SAMPLE_KEY = "is_sample_book"
SESSION_BRIEF_PATH_KEY = "session_brief_path"
SESSION_REPORTS_DIR_KEY = "session_reports_dir"

# A visitor's uploaded-book holdings.csv, kept so a later "Run brief" click can
# rebuild the same session book again without re-uploading.
SESSION_HOLDINGS_CSV_KEY = "session_holdings_csv_path"

# Set by "Run brief"/"Run screener" while still viewing the sample book — a
# session-scoped refresh of the artifacts, never a write to the committed
# data/sample/ files. Book identity (is_sample) is untouched.
SESSION_SAMPLE_REFRESH_BRIEF_KEY = "sample_refresh_brief_path"
SESSION_SAMPLE_REFRESH_REPORTS_KEY = "sample_refresh_reports_dir"


@dataclass(frozen=True)
class UIBookContext:
    book: list[Holding]
    is_sample: bool
    brief_path: str
    reports_dir: str


def resolve_ui_book_context() -> UIBookContext:
    """Resolve the book + artifact paths the UI should render this run.

    Priority:
      1. A session book explicitly flagged non-sample (``is_sample_book`` is
         ``False`` and the book is non-empty) — the visitor's upload.
      2. Otherwise the bundled sample book + committed sample artifacts.
    """
    session = st.session_state
    session_book = session.get(SESSION_BOOK_KEY)
    if session_book and session.get(SESSION_IS_SAMPLE_KEY) is False:
        return UIBookContext(
            book=session_book,
            is_sample=False,
            brief_path=session.get(SESSION_BRIEF_PATH_KEY, SAMPLE_BRIEF_PATH),
            reports_dir=session.get(SESSION_REPORTS_DIR_KEY, SAMPLE_REPORTS_DIR),
        )
    return UIBookContext(
        book=load_sample_book(),
        is_sample=True,
        brief_path=session.get(SESSION_SAMPLE_REFRESH_BRIEF_KEY, SAMPLE_BRIEF_PATH),
        reports_dir=session.get(SESSION_SAMPLE_REFRESH_REPORTS_KEY, SAMPLE_REPORTS_DIR),
    )
