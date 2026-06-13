"""Reusable hover-tooltip ('cloud') sourced from the single glossary."""

from __future__ import annotations

from html import escape

from adapters.visualization.components import glossary as _g


def tooltip(term: str, label: str | None = None) -> str:
    definition = _g.GLOSSARY[term]  # KeyError if undocumented — by design
    shown = escape(label if label is not None else term)
    return (
        f'<span class="ri-ttip">{shown}'
        f'<span class="ri-tip">{definition}</span></span>'
    )
