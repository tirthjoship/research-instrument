"""Attributed Google-AI read component for the Research Candidates tab (S6).

HONESTY HARD STOP:
  - build_case_context builds from supplied facts+news ONLY — no scores/composites/grades.
  - render_gemini_read renders a companion block BESIDE the score; it is NEVER an input.
  - The block carries an explicit attribution disclaimer: "summary beside the score — never an input".
  - FORBIDDEN_WORDS (buy/sell/winner/conviction/predict/alpha/outperform) are never emitted here.
"""

from __future__ import annotations

import html as _html

from domain.case_models import CaseContext, CaseResult


def build_case_context(
    ticker: str,
    facts: dict[str, str],
    news: list[dict[str, str]],
) -> CaseContext:
    """Build a CaseContext from already-fetched facts and news dicts.

    HONESTY INVARIANT: the returned CaseContext contains ONLY ticker, facts tuple,
    and news tuple. It NEVER carries composite, score, evidence_grade, or any derived
    metric — so Gemini cannot be influenced by or influence the score.

    Args:
        ticker: Stock ticker symbol.
        facts: Mapping of dimension label → fact text (e.g. {"occupancy": "recovering"}).
        news: List of dicts with at least a "title" key (and optionally "source").
    """
    facts_tuple = tuple(f"{key}: {value}" for key, value in facts.items() if value)
    news_tuple = tuple(
        (item.get("source", "news"), item["title"])
        for item in news
        if item.get("title")
    )
    # Explicitly only CaseContext fields: ticker, facts, news — no score fields.
    return CaseContext(ticker=ticker, facts=facts_tuple, news=news_tuple)


def render_gemini_read(result: CaseResult) -> str:
    """Render the .gai attributed Google-AI read block as HTML.

    The block is a companion BESIDE the score — never an input to any score,
    factor, or composite. This disclaimer is embedded in the rendered HTML.

    Returns:
        HTML string with the .gai block; or a note when data_gap is True.
    """
    if result.data_gap:
        return (
            '<div class="gai" style="font-size:10.5px;color:var(--text-muted);">'
            "&#128269; Google-AI read unavailable"
            "</div>"
        )

    # Build in-favor lines
    favor_items = "".join(
        f'<li style="margin:2px 0;">{_html.escape(p.text)}'
        f'<span style="font-size:9px;color:var(--text-muted);margin-left:4px;">'
        f"[{_html.escape(p.source_tag)}]</span></li>"
        for p in result.in_favor
    )
    favor_block = (
        f'<div style="margin-bottom:4px;">'
        f'<span style="color:#16a34a;font-weight:600;">&#9650; In favor</span>'
        f'<ul style="margin:2px 0 0 14px;padding:0;">{favor_items}</ul>'
        f"</div>"
        if result.in_favor
        else ""
    )

    # Build to-watch lines
    watch_items = "".join(
        f'<li style="margin:2px 0;">{_html.escape(p.text)}'
        f'<span style="font-size:9px;color:var(--text-muted);margin-left:4px;">'
        f"[{_html.escape(p.source_tag)}]</span></li>"
        for p in result.to_watch
    )
    watch_block = (
        f'<div style="margin-bottom:4px;">'
        f'<span style="color:#dc2626;font-weight:600;">&#9660; To watch</span>'
        f'<ul style="margin:2px 0 0 14px;padding:0;">{watch_items}</ul>'
        f"</div>"
        if result.to_watch
        else ""
    )

    return (
        '<div class="gai" style="font-size:10.5px;color:var(--text-secondary);'
        "background:#F7F5FF;border:1px solid #E4DCFB;border-radius:8px;"
        'padding:7px 10px;margin:8px 0 6px;">'
        "&#128269; <b>Google-AI read</b> "
        '<span style="color:var(--text-muted);font-size:9.5px;">'
        "(summary beside the score — never an input to the score)"
        "</span>"
        '<div style="margin-top:5px;">' + favor_block + watch_block + "</div>"
        "</div>"
    )


def render_gemini_read_two_col(result: CaseResult) -> str:
    """Render the .gai attributed Google-AI read block, Green/Red flags side by
    side in a two-column grid — Screener-local variant, approved via mockup
    2026-07-12. Home/Portfolio keep render_gemini_read()'s stacked layout;
    this is a display-only sibling, same honesty disclaimer and data_gap
    handling, never a shared-component edit.

    Item count always matches CaseResult.in_favor/to_watch exactly — never
    padded to hit a target count.
    """
    if result.data_gap:
        return render_gemini_read(result)

    favor_items = "".join(
        f'<li style="margin:2px 0;">{_html.escape(p.text)}'
        f'<span style="font-size:9px;color:var(--text-muted);margin-left:4px;">'
        f"[{_html.escape(p.source_tag)}]</span></li>"
        for p in result.in_favor
    )
    favor_col = (
        f'<div><span style="color:#16a34a;font-weight:600;">&#9650; Green flags</span>'
        f'<ul style="margin:2px 0 0 14px;padding:0;">{favor_items}</ul></div>'
        if result.in_favor
        else ""
    )

    watch_items = "".join(
        f'<li style="margin:2px 0;">{_html.escape(p.text)}'
        f'<span style="font-size:9px;color:var(--text-muted);margin-left:4px;">'
        f"[{_html.escape(p.source_tag)}]</span></li>"
        for p in result.to_watch
    )
    watch_col = (
        f'<div><span style="color:#dc2626;font-weight:600;">&#9660; Red flags</span>'
        f'<ul style="margin:2px 0 0 14px;padding:0;">{watch_items}</ul></div>'
        if result.to_watch
        else ""
    )

    return (
        '<div class="gai" style="font-size:10.5px;color:var(--text-secondary);'
        "background:#F7F5FF;border:1px solid #E4DCFB;border-radius:8px;"
        'padding:7px 10px;margin:8px 0 6px;">'
        "&#128269; <b>Google-AI read</b> "
        '<span style="color:var(--text-muted);font-size:9.5px;">'
        "(summary beside the score — never an input to the score)"
        "</span>"
        '<div style="display:grid;grid-template-columns:1fr 1fr;gap:12px;'
        'margin-top:5px;">' + favor_col + watch_col + "</div>"
        "</div>"
    )
