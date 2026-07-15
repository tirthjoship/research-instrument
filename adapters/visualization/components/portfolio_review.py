"""Needs-review collapsed cards for the portfolio tab.

Each card is an inspect-anchor; clicking sets ?inspect=TICKER and the tab
renders the shared detail panel (reusing decision_card.render_expanded_card).
"""

from __future__ import annotations

from adapters.visualization.portfolio_view import PortfolioRow

_CLS = {"REDUCE": "reduce", "TRIM": "trim", "REVIEW": "review"}
_PILL = {
    "REDUCE": ("#FEE2E2", "#991B1B"),
    "TRIM": ("#FEF3C7", "#92400E"),
    "REVIEW": ("#DBEAFE", "#1E40AF"),
}


def build_review_card_html(row: PortfolioRow) -> str:
    cls = _CLS.get(row.verdict, "review")
    bg, fg = _PILL.get(row.verdict, ("#F1F5F9", "#475569"))
    pnl_color = "#16A34A" if row.pnl >= 0 else "#DC2626"
    sign = "+" if row.pnl >= 0 else ""
    why = row.why or "Discipline rule fired — review."
    # The outer element must be a block-level tag (div) — CommonMark only
    # recognizes a fixed set of block-starting tags for raw-HTML passthrough,
    # and <a> isn't one of them. Opening the string with <a> made Streamlit's
    # markdown renderer fragment the card into a stray empty anchor plus one
    # duplicated <a> per inner <div> (each independently picking up the
    # .pf-review border). Nesting the <a> inside a <div> keeps the whole card
    # as a single raw-HTML block.
    return (
        f'<div class="pf-review {cls}">'
        f'<a href="?inspect={row.ticker}" target="_self" '
        f'style="text-decoration:none;color:inherit;display:block;">'
        '<div style="display:flex;align-items:center;gap:.6rem;flex-wrap:wrap;">'
        f"<span style=\"font-family:'Fraunces',serif;font-weight:700;font-size:1.1rem;\">{row.ticker}</span>"
        f'<span style="color:var(--ri-muted);font-size:.76rem;">{row.weight:.1f}% · {row.sector}</span>'
        f'<span style="padding:2px 8px;border-radius:11px;font-size:.66rem;font-weight:700;'
        f'background:{bg};color:{fg};">{row.verdict}</span>'
        f"<span style=\"margin-left:auto;font-family:'IBM Plex Mono',monospace;"
        f'font-weight:700;color:{pnl_color};">{sign}{row.pnl:.1f}%</span>'
        "</div>"
        f'<div style="margin-top:5px;font-size:.8rem;color:#334155;">{why}</div>'
        '<div style="margin-top:5px;font-size:.72rem;color:var(--ri-teal);">'
        "▾ click for full detail (RAG · rubric · case)</div>"
        "</a>"
        "</div>"
    )


def build_calm_html() -> str:
    return (
        '<div style="border:1px solid #A7F3D0;background:#F0FDF4;border-radius:10px;'
        'padding:14px 16px;display:flex;align-items:center;gap:11px;">'
        '<div style="width:26px;height:26px;border-radius:50%;background:#16A34A;'
        "color:#fff;display:flex;align-items:center;justify-content:center;"
        'font-weight:700;">&#10003;</div>'
        '<div><div style="font-weight:600;">Nothing needs review</div>'
        '<div style="font-size:.82rem;color:#166534;">'
        "All positions are HOLD — sizes look appropriate against the discipline rule."
        "</div></div></div>"
    )
