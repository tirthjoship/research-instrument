"""Reusable styled card components for dashboard.

Uses HTML with CSS classes defined in styles.py.
"""

from __future__ import annotations

from typing import Any

from adapters.visualization.components.formatters import (
    confidence_bar_html,
    grade_badge_html,
    signal_pill_html,
    urgency_badge,
)


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
    urgency_label = urgency_badge(urgency)

    st.markdown(
        f'<div class="dashboard-card {card_class}">'
        f"<strong>{action_type.upper()} {symbol}</strong>{grade_html}<br>"
        f'<span style="color: #6B7280; font-size: 14px;">{reason}</span><br>'
        f'<span style="font-size: 13px;">{urgency_label}</span>'
        f"{conf_html}"
        f"</div>",
        unsafe_allow_html=True,
    )


def render_signal_layer_card(
    st: Any,
    layer_name: str,
    layer_key: str,
    signal_direction: str,
    details: dict[str, str],
) -> None:
    """Render a signal layer card with colored top border."""
    layer_class = f"layer-{layer_key}"
    signal_html = (
        signal_pill_html(signal_direction)
        if signal_direction != "—"
        else '<span style="color: #9E9E9E;">No data</span>'
    )

    details_html = ""
    for k, v in details.items():
        details_html += f'<div style="font-size: 13px; color: #6B7280; margin-top: 4px;"><strong>{k}:</strong> {v}</div>'

    st.markdown(
        f'<div class="layer-card {layer_class}">'
        f'<div style="font-size: 15px; font-weight: 600; margin-bottom: 6px;">{layer_name}</div>'
        f"<div>{signal_html}</div>"
        f"{details_html}"
        f"</div>",
        unsafe_allow_html=True,
    )


def render_info_section(
    st: Any,
    title: str,
    subtitle: str,
    info_text: str,
) -> None:
    """Render a section header with subtitle and info expander."""
    st.markdown(f"### {title}")
    st.markdown(f'<p class="section-subtitle">{subtitle}</p>', unsafe_allow_html=True)
    with st.expander("ℹ️ Learn more"):
        st.markdown(info_text)
