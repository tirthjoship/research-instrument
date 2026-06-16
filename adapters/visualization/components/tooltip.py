"""Reusable hover-tooltip ('cloud') sourced from the single glossary."""

from __future__ import annotations

from html import escape

from adapters.visualization.components import glossary as _g


def tooltip(term: str, label: str | None = None) -> str:
    """Hover-tooltip span sourced from the glossary.

    When *label* is None the term text is shown with a trailing grey circle badge.
    When *label* is "ⓘ" only the circle badge is rendered (no text label) — use
    this for icon-only contexts such as bucket-header and tile labels in the
    screener (mockup .ic spec).
    """
    definition = _g.GLOSSARY[term]  # KeyError if undocumented — by design
    _circle = (
        '<span style="'
        "display:inline-flex;align-items:center;justify-content:center;"
        "width:13px;height:13px;border-radius:50%;background:#CBD5E1;"
        "color:#fff;font-size:8px;font-weight:700;font-style:normal;"
        "margin-left:4px;vertical-align:middle;cursor:help;"
        'line-height:1;flex-shrink:0;">i</span>'
    )
    if label == "ⓘ":
        # pure circle badge — no text
        shown: str = _circle
    elif label is None:
        # term text + trailing circle badge
        shown = escape(term) + _circle
    else:
        shown = escape(label)
    return (
        f'<span class="ri-ttip">{shown}'
        f'<span class="ri-tip">{definition}</span></span>'
    )
