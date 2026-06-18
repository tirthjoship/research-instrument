"""Tab composition — _compose() and render() entry point."""

from __future__ import annotations

from typing import Any

import streamlit as st

from adapters.visualization.components.risk_second_opinion import (
    render_risk_second_opinion,
)
from adapters.visualization.data_loader import load_brief_summary

from ._theme import _MUT
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
from .evidence import _evidence_bands, _flags_footer, _grill_drill
from .factor_chart import _factor_chart
from .sections import _drift, _sector_section, _teach, _who_owns


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

    parts = [
        _header(),
        _status_banner(flags),
        _contract_legend(),
        _vitals(macro),
        _lens_nav(),
        _standing(macro),
        _dials(macro),
        _grill_drill(flags),
        _evidence_bands(macro),
        _factor_chart(macro),
        _enb_section(macro),
        _sector_section(macro),
        _who_owns(macro),
        _drift(macro),
    ]
    # Mockup order: _drift → [Second opinion · Google AI] → _teach → _flags_footer
    if ai_html:
        parts.append(ai_html)
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


def render(path: str = "data/personal/brief_summary.json") -> None:
    """Streamlit entrypoint: load macro → render v8 status-first layout."""
    summary = load_brief_summary(path)
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
