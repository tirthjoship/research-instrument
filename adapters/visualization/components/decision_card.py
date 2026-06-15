"""Decision-card component: collapsed row + expanded v9 card. Returns HTML strings.

Squares use a BESPOKE per-ticker hover (RagSignal.detail), NOT tooltip()/GLOSSARY —
the detail is per-ticker data, not a glossary term, so tooltip() would KeyError.
"""

from __future__ import annotations

import html as _html
from typing import Any

from application.evidence_card import EvidenceCard
from domain.discipline import Verdict
from domain.evidence_rag import RagColor, RagSignal  # noqa: F401

_RAG_CLASS = {
    RagColor.RED: "r",
    RagColor.AMBER: "a",
    RagColor.GREEN: "g",
    RagColor.GAP: "gap",
}


def _squares_html(card: EvidenceCard) -> str:
    cells = []
    for sig in card.signals:  # already fixed DIMENSIONS order
        cls = _RAG_CLASS[sig.color]
        tip = _html.escape(f"{sig.dimension} — {sig.detail}")
        cells.append(
            f'<span class="dc-sq {cls}"><span class="dc-tip">{tip}</span></span>'
        )
    return f'<span style="display:inline-flex;gap:3px">{"".join(cells)}</span>'


def _sparkline_svg(prices: tuple[float, ...]) -> str:
    if not prices:
        return '<span class="dc-spark"></span>'
    lo, hi = min(prices), max(prices)
    rng = (hi - lo) or 1.0
    n = len(prices)
    pts = " ".join(
        f"{round(i / max(n - 1, 1) * 80, 1)},{round(26 - (p - lo) / rng * 24, 1)}"
        for i, p in enumerate(prices)
    )
    color = "#1F9254" if prices[-1] >= prices[0] else "#CE2F26"
    return (
        f'<svg class="dc-spark" viewBox="0 0 80 28" preserveAspectRatio="none">'
        f'<polyline fill="none" stroke="{color}" stroke-width="1.7" points="{pts}"/></svg>'
    )


def render_collapsed_row(
    card: EvidenceCard,
    *,
    verdict: Verdict,
    name: str,
    unrealized_pct: float | None,
    oneliner: str,
) -> str:
    pct = "—" if unrealized_pct is None else f"{unrealized_pct:+.1f}%"
    pct_color = "#1F9254" if (unrealized_pct or 0) >= 0 else "#CE2F26"
    return (
        f'<div class="dc-row">'
        f'<div class="dc-tk" style="width:106px"><b>{_html.escape(card.ticker)}</b>'
        f"<span>{_html.escape(name)}</span></div>"
        f'<span class="badge">{verdict.value}</span>'
        f"{_squares_html(card)}"
        f"{_sparkline_svg(card.sparkline)}"
        f'<div style="flex:1;font-size:12.5px;color:var(--ri-muted)">{_html.escape(oneliner)}</div>'
        f'<div style="font-weight:700;color:{pct_color};width:64px;text-align:right">{pct}</div>'
        f"</div>"
    )


_RAG_LETTER = {
    RagColor.RED: ("R", "#CE2F26"),
    RagColor.AMBER: ("A", "#C9810E"),
    RagColor.GREEN: ("G", "#1F9254"),
    RagColor.GAP: ("·", "#94A8AD"),
}


def _rag_table_html(card: EvidenceCard) -> str:
    rows = []
    for s in card.signals:
        letter, color = _RAG_LETTER[s.color]
        rows.append(
            f'<tr><td style="width:22px"><span style="display:inline-block;width:14px;height:14px;'
            f"border-radius:3px;background:{color};color:#fff;font-size:9px;font-weight:800;"
            f'text-align:center;line-height:14px">{letter}</span></td>'
            f'<td style="font-weight:600;width:104px">{_html.escape(s.dimension)}</td>'
            f'<td style="color:var(--ri-muted)">{_html.escape(s.detail)}</td></tr>'
        )
    return (
        "<div style=\"font-family:'IBM Plex Mono';font-size:10px;letter-spacing:.1em;"
        'text-transform:uppercase;color:var(--ri-muted);margin-bottom:5px">Evidence detail — the 5 squares, in full</div>'
        '<table style="width:100%;font-size:12px;border-collapse:collapse;margin-bottom:13px">'
        f'{"".join(rows)}</table>'
    )


def _case_html(case: Any | None) -> str:
    hd = (
        '<div class="dc-case-hd"><span>The case — Google AI, from cited sources</span>'
        '<span class="dc-case-badge">informs you, not the verdict</span></div>'
    )
    if case is None:
        body = (
            '<div style="padding:14px;color:var(--ri-muted);font-size:11.5px">'
            "The case loads when you open this card — summarised from cited articles only.</div>"
        )
        return f'<div class="dc-case">{hd}{body}</div>'
    favor = "<br>".join(
        f'{i + 1}. {_html.escape(p.text)} <span style="color:#94A8AD">[{_html.escape(p.source_tag)}]</span>'
        for i, p in enumerate(case.in_favor)
    )
    watch = "<br>".join(
        f'{i + 1}. {_html.escape(p.text)} <span style="color:#94A8AD">[{_html.escape(p.source_tag)}]</span>'
        for i, p in enumerate(case.to_watch)
    )
    cols = (
        f'<div class="dc-cols"><div><div class="dc-ch" style="color:#1F9254">▲ in its favor</div>'
        f'<div style="font-size:11.5px;line-height:1.75">{favor}</div></div>'
        f'<div><div class="dc-ch" style="color:#CE2F26">▼ to watch out for</div>'
        f'<div style="font-size:11.5px;line-height:1.75">{watch}</div></div></div>'
    )
    foot = (
        '<div style="font-size:10.5px;color:var(--ri-muted);padding:8px 12px;background:#fbfdfd">'
        "Summarised from real fetched articles (each cited). Both sides on purpose — doesn't pick for you.</div>"
    )
    return f'<div class="dc-case">{hd}{cols}{foot}</div>'


def render_expanded_card(
    card: EvidenceCard,
    *,
    case: Any | None,
    verdict: Verdict,
    name: str,
    unrealized_pct: float | None,
    means: str,
    price: float | None,
    cost: float | None,
    returns: tuple[float, ...],
    reliability: str,
) -> str:
    pct = "—" if unrealized_pct is None else f"{unrealized_pct:+.1f}%"
    ret = " · ".join(f"{r:+.1f}" for r in returns) if returns else "—"
    return (
        '<div class="dc-card-inner">'
        f'<div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:8px">'
        f'<div><span style="font-family:Fraunces,serif;font-size:21px;font-weight:800">{verdict.value}</span>'
        f'<span style="font-size:12px;color:var(--ri-muted);margin-left:8px">trend-break rule (v1) — review prompt, not a forecast</span></div></div>'
        f'<div style="background:#e6f1f3;border:1px solid #cfe6ec;border-radius:8px;padding:11px 13px;'
        f'font-size:13.5px;line-height:1.55;margin-bottom:13px"><b style="color:#0a5260">What this means:</b> {_html.escape(means)}</div>'
        f'<div style="display:flex;gap:8px;margin-bottom:13px;font-size:12px">'
        f'<div style="flex:1;background:#f4f8f9;border-radius:7px;padding:7px 9px">Price<br><b>{price if price else "—"}</b></div>'
        f'<div style="flex:1;background:#f4f8f9;border-radius:7px;padding:7px 9px">Your cost<br><b>{cost if cost else "—"}</b></div>'
        f'<div style="flex:1;background:#eafaf3;border-radius:7px;padding:7px 9px">Unrealized<br><b>{pct}</b></div>'
        f'<div style="flex:2;background:#f4f8f9;border-radius:7px;padding:7px 9px">7/30/90/180d<br><b>{ret}</b></div></div>'
        f"{_case_html(case)}"
        f"{_rag_table_html(card)}"
        f'<div class="dc-learn"><h4 style="margin:0 0 5px;font-size:13px">How this verdict learns &amp; gets multi-factor</h4>'
        f'<p style="margin:0;font-size:12px;line-height:1.5">Today it\'s the <b>trend-break rule (v1)</b>; it improves by '
        f"<b>experiment</b> and is adopted only when it beats v1.</p>"
        f'<div style="font-size:11px;color:var(--ri-muted);margin-top:7px;border-top:1px dashed #cfe6ec;padding-top:6px">'
        f"<b>Reliability:</b> {_html.escape(reliability)}. From outcomes, never the AI case.</div></div>"
        f'<div style="font-size:10px;color:var(--ri-muted);border-top:1px dashed var(--ri-line);padding-top:7px">'
        f"Research only · attributed evidence + your rule's measured history · not a trade signal.</div>"
        "</div>"
    )
