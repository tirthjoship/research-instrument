"""Tab composition — _compose() and render() entry point."""

from __future__ import annotations

from typing import Any

import streamlit as st

from adapters.visualization.book_context import resolve_ui_book_context
from adapters.visualization.components.risk_second_opinion import (
    render_risk_second_opinion,
)
from adapters.visualization.data_loader import load_brief_summary

from ._theme import _MUT, _PETROL
from .components import (
    _contract_legend,
    _dials,
    _header,
    _lens_nav,
    _standing,
    _status_banner,
    _vitals,
)
from .enb_section import _enb_section
from .evidence import _benchmark, _evidence_bands, _flags_footer, _grill_drill
from .factor_chart import _factor_chart
from .sections import _decision_levers, _drift, _sector_section, _teach, _who_owns


def _fold(eyebrow: str, title: str, html: str, *, section_id: str = "") -> str:
    """Wrap *html* in a collapsed-by-default disclosure (mockup: 5-10 min scan mode).

    Reuses the existing ``.teach``/``.tbody`` accordion styling (already shipped
    for the Q&A walkthrough) so the deep-dive sections read as optional detail
    rather than required reading on first load.
    """
    id_attr = f' id="{section_id}"' if section_id else ""
    return (
        f'<div class="ri-sec"{id_attr}>'
        f'<span style="color:{_PETROL}">{eyebrow}</span> &middot; {title}</div>'
        '<details class="teach">'
        f'<summary><span class="h">{title}</span><span>&#43;</span></summary>'
        f'<div class="tbody">{html}</div>'
        "</details>"
    )


def _compose(macro: dict[str, Any] | None, ai_html: str = "") -> str:
    """Compose the full Risk-tab HTML.

    Args:
        macro:    the macro dict from load_brief_summary(), or None.
        ai_html:  optional pre-rendered HTML for the Google-AI second-opinion
                  panel.  When non-empty it is injected between the drift
                  section and the teach section (matching mockup order).
                  Ignored (not inserted) when empty / falsy — _compose stays
                  fully testable without a live CaseResult.

    Returns:
        Complete HTML string (safe to pass to st.markdown(unsafe_allow_html=True)).
        Never raises — degrades gracefully to safe-fallback when macro is None.
    """
    if macro is None:
        return (
            '<div class="ri-h1">Portfolio Risk</div>'
            f'<p style="color:{_MUT}">No macro-beta data. '
            "Run <code>python -m application.cli weekly-brief</code> "
            "(the scrubber runs inside it).</p>"
        )

    flags: list[str] = list(macro.get("flags") or [])

    # Glance layer — always visible. Answers "what's good, what's not" in one
    # screen: banner, colour-coded vitals, standing narrative, gauge dials.
    parts = [
        _header(),
        _status_banner(flags),
        _contract_legend(),
        _vitals(macro),
        _lens_nav(),
        _standing(macro),
        _dials(macro),
    ]

    # Deep-dive layer — grouped into collapsed disclosures so a 5-10 minute
    # read isn't forced to scroll past methodology to find the verdict.
    parts.append(
        _fold(
            "The Evidence",
            "How you compare & what's driving it",
            _grill_drill(flags)
            + _evidence_bands(macro)
            + _benchmark(macro)
            + _factor_chart(macro)
            + _enb_section(macro),
            section_id="evidence-fold",
        )
    )
    parts.append(
        _fold(
            "The Book",
            "Sector concentration & who owns the bet",
            _sector_section(macro) + _who_owns(macro),
            section_id="breakdown-fold",
        )
    )
    decision_html = _decision_levers(macro) + _drift(macro)
    if ai_html:
        decision_html += ai_html
    parts.append(
        _fold(
            "The Levers",
            "What would change it & second opinion",
            decision_html,
            section_id="levers-fold",
        )
    )

    parts += [
        _teach(macro),
        _flags_footer(
            flags,
            macro.get("coverage_holdings", "?"),
            macro.get("total_holdings", "?"),
        ),
    ]
    return "\n".join(parts)


# ===========================================================================
# Streamlit entrypoint
# ===========================================================================


def render(path: str | None = None) -> None:
    """Streamlit entrypoint: load macro → render v8 status-first layout.

    ``path`` defaults to the book-context resolver's brief path (sample on
    cold start, session brief after an upload) — never data/personal/ unless
    a caller explicitly passes that path.
    """
    effective_path = path if path is not None else resolve_ui_book_context().brief_path
    summary = load_brief_summary(effective_path)
    macro = (summary or {}).get("macro") if summary else None

    # Build AI second-opinion panel HTML BEFORE composing (spec §9 — no live
    # Gemini at render time; cache-first load only).  ai_html is "" when
    # off-local or cache empty — _compose ignores empty strings.
    ai_html = ""
    if macro is not None:
        from application.risk_second_opinion import load_cached_risk_second_opinion

        ai_html = render_risk_second_opinion(load_cached_risk_second_opinion())

    # Single st.markdown call — ensures mockup order:
    #   _drift → Second opinion · Google AI → _teach → _flags_footer
    st.markdown(_compose(macro, ai_html), unsafe_allow_html=True)

    # Lens-nav smooth-scroll shim — native hash anchors rerun the app instead of
    # scrolling; this intercepts the bean click client-side (see lens_scroll.py).
    if macro is not None:
        from adapters.visualization.components.lens_scroll import render_lens_scroll

        render_lens_scroll()
