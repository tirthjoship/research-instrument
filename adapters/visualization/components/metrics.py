"""Reusable styled card components for dashboard.

Uses HTML with CSS classes defined in styles.py.
"""

from __future__ import annotations

from typing import Any

from adapters.visualization.components.formatters import (
    confidence_bar_html,
    grade_badge_html,
    signal_pill_html,
    urgency_pill_html,
)


def render_hero_banner(
    st: Any,
    verdict: str,
    portfolio_value: float | None = None,
    n_positions: int = 0,
) -> None:
    """Render the Command Center hero banner."""
    portfolio_html = ""
    if portfolio_value is not None and n_positions > 0:
        portfolio_html = (
            f'<div style="font-size: 13px; color: #6B7280; margin-top: 8px;">'
            f"${portfolio_value:,.0f} across {n_positions} positions"
            f"</div>"
        )

    st.markdown(
        f'<div class="hero-card">'
        f'<div style="font-size: 16px; font-weight: 500; color: #111827;">{verdict}</div>'
        f"{portfolio_html}"
        f"</div>",
        unsafe_allow_html=True,
    )


def render_verdict_card(
    st: Any,
    verdict: str,
    tone: str = "neutral",
    details: str = "",
) -> None:
    """Render a verdict card with contextual background color.

    tone: 'positive', 'negative', or 'neutral'
    """
    css_class = f"verdict-{tone}"
    details_html = (
        f'<div style="font-size: 13px; color: #6B7280; margin-top: 8px;">{details}</div>'
        if details
        else ""
    )

    st.markdown(
        f'<div class="verdict-card {css_class}">'
        f'<div style="font-size: 15px; color: #111827;">{verdict}</div>'
        f"{details_html}"
        f"</div>",
        unsafe_allow_html=True,
    )


def render_inline_context(st: Any, text: str) -> None:
    """Render inline context text below a section header — replaces st.expander."""
    st.markdown(f'<p class="inline-context">{text}</p>', unsafe_allow_html=True)


def render_action_card(
    st: Any,
    action_type: str,
    symbol: str,
    reason: str,
    urgency: str,
    confidence: float | None = None,
    grade: str | None = None,
) -> None:
    """Render a styled action card with left color border."""
    card_class = {
        "SELL": "card-sell",
        "BUY": "card-buy",
        "WATCH": "card-watch",
    }.get(action_type.upper(), "card-info")

    grade_html = f" {grade_badge_html(grade)}" if grade else ""
    conf_html = confidence_bar_html(confidence) if confidence is not None else ""
    urgency_html = urgency_pill_html(urgency)

    st.markdown(
        f'<div class="dashboard-card {card_class}">'
        f"<strong>{action_type.upper()} {symbol}</strong>{grade_html}<br>"
        f'<span style="color: #6B7280; font-size: 14px;">{reason}</span><br>'
        f'<span style="font-size: 13px;">{urgency_html}</span>'
        f"{conf_html}"
        f"</div>",
        unsafe_allow_html=True,
    )


def render_signal_layer_card(
    st: Any,
    layer_name: str,
    layer_key: str,
    signal_direction: str,
    verdict: str,
    details: dict[str, str],
) -> None:
    """Render a signal layer card with colored top border and verdict."""
    layer_class = f"layer-{layer_key}"
    signal_html = (
        signal_pill_html(signal_direction)
        if signal_direction not in ("—", "not_run")
        else '<span style="color: #9CA3AF; font-size: 13px;">Not yet run</span>'
    )

    details_html = ""
    for k, v in details.items():
        details_html += (
            f'<div style="font-size: 13px; color: #6B7280; margin-top: 4px;">'
            f"<strong>{k}:</strong> {v}</div>"
        )

    st.markdown(
        f'<div class="layer-card {layer_class}">'
        f'<div style="font-size: 15px; font-weight: 600; margin-bottom: 4px;">{layer_name}</div>'
        f"<div>{signal_html}</div>"
        f'<div style="font-size: 13px; color: #6B7280; margin: 6px 0;">{verdict}</div>'
        f"{details_html}"
        f"</div>",
        unsafe_allow_html=True,
    )


def render_pick_card(
    st: Any,
    rank: int,
    symbol: str,
    grade: str,
    verdict: str,
    predicted_5d: str,
    confidence: float | None,
    layer_dots: str,
    sources: str,
) -> None:
    """Render a full pick card for top 5 opportunities."""
    grade_html = grade_badge_html(grade)
    conf_html = confidence_bar_html(confidence) if confidence is not None else ""

    st.markdown(
        f'<div class="dashboard-card card-buy" style="border-left-width: 4px;">'
        f'<div style="display: flex; justify-content: space-between; align-items: center;">'
        f'<span style="font-size: 18px; font-weight: 700;">#{rank} {symbol}</span>'
        f"<span>{grade_html}</span>"
        f"</div>"
        f'<div style="font-size: 14px; color: #374151; margin: 8px 0;">{verdict}</div>'
        f'<div style="font-size: 13px; color: #6B7280;">5d: {predicted_5d} {conf_html}</div>'
        f'<div style="font-size: 12px; color: #9CA3AF; margin-top: 6px;">{layer_dots}</div>'
        f'<div style="font-size: 12px; color: #9CA3AF; margin-top: 2px;">Sources: {sources}</div>'
        f"</div>",
        unsafe_allow_html=True,
    )
