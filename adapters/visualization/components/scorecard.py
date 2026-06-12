"""Ranked scorecard rows for the Screener's check-your-own-list feature.

Evidence + fit language only — the vocabulary-guard test scans this module.
"""

from __future__ import annotations

import html
from typing import TYPE_CHECKING, Any, Sequence

import streamlit as st

if TYPE_CHECKING:
    from application.batch_fit_use_case import BatchFitRow

_GRADE_ORDER = {"STRONG": 0, "MODERATE": 1, "WEAK": 2, "UNKNOWN": 3}
_GRADE_COLOR = {
    "STRONG": "#15803D",
    "MODERATE": "#B45309",
    "WEAK": "#B91C1C",
    "UNKNOWN": "#5C6370",
}
_FLAG_GLYPH = {
    "BETA_AMPLIFY": "▲",
    "CONCENTRATION": "◔",
    "TREND_STATE": "◆",
    "DATA_GAP": "▢",
}


def rank_rows(rows: "Sequence[BatchFitRow]") -> "list[BatchFitRow]":
    return sorted(rows, key=lambda r: _GRADE_ORDER.get(r.verdict.evidence_grade, 9))


def _flag_icons(row: "BatchFitRow") -> str:
    parts = []
    for f in row.verdict.fit_flags:
        glyph = _FLAG_GLYPH.get(f.kind, "·")
        parts.append(
            f'<span class="tip" data-tip="{html.escape(f.message, quote=True)}"'
            f' style="margin-right:6px;">{glyph}</span>'
        )
    return "".join(parts)


def render_scorecard(rows: "Sequence[BatchFitRow]", st_module: Any = st) -> None:
    for i, row in enumerate(rank_rows(rows), start=1):
        grade = row.verdict.evidence_grade
        color = _GRADE_COLOR.get(grade, "#5C6370")
        st_module.markdown(
            f'<div class="ws-card" style="padding:10px 16px;display:flex;'
            f'align-items:center;gap:14px;">'
            f'<span style="color:#5C6370;font-weight:700;">#{i}</span>'
            f'<span style="font-weight:700;font-size:16px;">{row.ticker}</span>'
            f'<span style="background:{color};color:#fff;border-radius:999px;'
            f'padding:2px 10px;font-size:12px;font-weight:700;">{grade}</span>'
            f'<span style="font-size:14px;">{_flag_icons(row)}</span>'
            f'<span style="color:#5C6370;font-size:13px;flex:1;">'
            f"{html.escape(row.verdict.summary)}</span>"
            f"</div>",
            unsafe_allow_html=True,
        )
    st_module.caption(
        "Evidence + fit vs your book — this engine makes no trade calls "
        "(see the Trust tab)."
    )
