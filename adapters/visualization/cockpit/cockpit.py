"""Cockpit assembler — single-scroll family surface, strict priority order.

Sections render top-to-bottom: danger, your calls, week retro, look-into-next,
lookup. Each section degrades gracefully when its artifact is missing.
"""

from __future__ import annotations

import streamlit as st

from adapters.visualization.cockpit import (  # noqa: F401  (re-exported for tests)
    _calls,
    _danger,
    _discover,
    _lookup,
    _retro,
)

SUMMARY_PATH = "data/personal/brief_summary.json"
REPORTS_DIR = "data/reports"
HOLDINGS_PATH = "data/personal/holdings.csv"
DISCIPLINE_LOG_PATH = "data/personal/discipline_log.jsonl"
ADHERENCE_LOG_PATH = "data/personal/adherence_log.jsonl"
HISTORY_DIR = "data/personal/brief_history"


def render(
    summary_path: str = SUMMARY_PATH,
    reports_dir: str = REPORTS_DIR,
    holdings_path: str = HOLDINGS_PATH,
    discipline_log_path: str = DISCIPLINE_LOG_PATH,
    adherence_log_path: str = ADHERENCE_LOG_PATH,
    history_dir: str = HISTORY_DIR,
) -> None:
    st.markdown('<div id="cp-danger"></div>', unsafe_allow_html=True)
    _danger.render(summary_path=summary_path, discipline_log_path=discipline_log_path)

    st.markdown('<div id="cp-calls"></div>', unsafe_allow_html=True)
    _calls.render(
        summary_path=summary_path,
        holdings_path=holdings_path,
        discipline_log_path=discipline_log_path,
        history_dir=history_dir,
    )

    st.markdown('<div id="cp-retro"></div>', unsafe_allow_html=True)
    _retro.render(
        summary_path=summary_path,
        holdings_path=holdings_path,
        adherence_log_path=adherence_log_path,
        history_dir=history_dir,
    )

    st.markdown('<div id="cp-discover"></div>', unsafe_allow_html=True)
    _discover.render(
        summary_path=summary_path,
        reports_dir=reports_dir,
        holdings_path=holdings_path,
    )

    st.markdown('<div id="cp-lookup"></div>', unsafe_allow_html=True)
    _lookup.render(reports_dir=reports_dir, summary_path=summary_path)
