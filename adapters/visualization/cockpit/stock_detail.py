"""Stock-detail drawer — fit verdict + evidence grade + snowflake + present facts.

Ported intact from tabs/stock_analysis.py: _ensure_fit_cached, _render_fit_card,
_snowflake_axes. Wrapped in st.dialog; opened from any cockpit row or lookup.
"""

from __future__ import annotations

from collections.abc import Callable, MutableMapping
from typing import TYPE_CHECKING, Any

import streamlit as st
from loguru import logger

if TYPE_CHECKING:
    from domain.fit import FitVerdict

from adapters.visualization.components.snowflake import build_snowflake
from adapters.visualization.data_loader import load_latest_screen  # noqa: F401
from domain.fit import FitVerdict

# === BEGIN verbatim ports from tabs/stock_analysis.py (lines 65, 257, 675) ===

_SEVERITY_CLASS = {
    "INFO": "verdict-neutral",
    "CAUTION": "verdict-caution",
    "WARNING": "verdict-negative",
}


def _ensure_fit_cached(
    session_state: MutableMapping[str | int, Any],
    key: str,
    compute_fn: Callable[[], "FitVerdict"],
) -> "FitVerdict | None":
    """Compute the fit verdict once per key; cache in session_state.

    On compute failure, return None and do NOT cache (so a later rerun retries).
    """
    if key in session_state:
        return session_state[key]
    try:
        verdict = compute_fn()
    except Exception:
        logger.warning("fit verdict computation failed")
        return None
    session_state[key] = verdict
    return verdict


def _render_fit_card(verdict: FitVerdict, screen_as_of: str | None = None) -> None:
    """Evidence grade + fit flags. Descriptive arithmetic only — never a forecast."""
    from adapters.visualization.components.formatters import grade_badge_html

    stale = f" · screen as of {screen_as_of}" if screen_as_of else ""
    st.markdown(
        f'<div class="ws-card" style="padding:12px 16px;margin-bottom:12px;">'
        f"{grade_badge_html(verdict.evidence_grade)} "
        f'<span style="font-weight:700;">Evidence + fit vs your book</span>'
        f'<span style="color:#64748B;font-size:12px;">{stale}</span>'
        f'<div style="font-size:14px;margin-top:8px;">{verdict.summary}</div>'
        "</div>",
        unsafe_allow_html=True,
    )
    for flag in verdict.fit_flags:
        css = _SEVERITY_CLASS.get(flag.severity, "verdict-neutral")
        st.markdown(
            f'<div class="verdict-card {css}">'
            f'<div style="font-size:14px;color:#111827;">{flag.message}</div>'
            "</div>",
            unsafe_allow_html=True,
        )
    st.caption(
        "Evidence + fit only — this tool does not forecast returns "
        "(see Trust). Position weights are by cost basis."
    )


def _snowflake_axes(fit: "FitVerdict | None") -> dict[str, float]:
    """Descriptive axes from the latest screen row + fit verdict. Empty dict
    when fit is None (snowflake hidden). Book fit is always computed when fit
    is present; factor axes are added only when the ticker is in the screen."""
    axes: dict[str, float] = {}
    if fit is None:
        return axes
    screen = load_latest_screen("data/reports")
    if screen:
        cand = next(
            (c for c in screen.get("candidates", []) if c.get("ticker") == fit.ticker),
            None,
        )
        if cand:
            for fs in cand.get("factor_scores", []):
                name = str(fs.get("name", "")).title()
                if name in ("Value", "Quality", "Momentum", "Revision"):
                    axes["Valuation" if name == "Value" else name] = (
                        float(fs.get("percentile", 0.0)) * 100
                    )
            th = cand.get("trend_health")
            if isinstance(th, (int, float)):
                # trend_health in [-1,1] -> [0,100], 50 = neutral midpoint.
                axes["Trend"] = max(0.0, min(100.0, 50.0 + float(th) * 50.0))
    # WARNING flags cost 2x CAUTION; descriptive book-fit deduction only.
    penalty = sum(
        30.0 if f.severity == "WARNING" else 15.0 if f.severity == "CAUTION" else 0.0
        for f in fit.fit_flags
    )
    axes["Book fit"] = max(0.0, 100.0 - penalty)
    return axes


# === END verbatim ports ===


@st.dialog("Stock detail", width="large")
def open_stock_detail(ticker: str) -> None:
    from application.batch_fit_use_case import default_fit_fn

    fit = _ensure_fit_cached(
        st.session_state,
        f"fit_{ticker}",
        lambda: default_fit_fn(ticker),
    )
    if fit is not None:
        _render_fit_card(fit)
        axes = _snowflake_axes(fit)
        fig = build_snowflake(axes) if axes else None
        if fig is not None:
            st.plotly_chart(fig, use_container_width=True)
    else:
        st.warning(f"Could not load fit data for {ticker}.")
    st.caption(
        "Evidence + fit only — descriptive present-day facts; "
        "the gate verdict lives on the cockpit."
    )
