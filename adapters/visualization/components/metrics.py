"""Reusable metric card and action card components for dashboard.

These are thin Streamlit wrappers. Tested via smoke import test.
"""

from __future__ import annotations

from typing import Any

from adapters.visualization.components.formatters import urgency_badge


def render_metric(
    st: Any,
    label: str,
    value: str,
    delta: str | None = None,
    help_text: str | None = None,
) -> None:
    """Render a metric card using st.metric()."""
    st.metric(label=label, value=value, delta=delta, help=help_text)


def render_action_card(
    st: Any,
    action_type: str,
    symbol: str,
    reason: str,
    urgency: str,
    confidence: float | None = None,
) -> None:
    """Render an action card (sell signal or buy opportunity)."""
    badge = urgency_badge(urgency)
    action_colors = {"SELL": "red", "WATCH": "orange", "BUY": "green"}
    color = action_colors.get(action_type.upper(), "blue")
    conf_str = f" | Confidence: {confidence:.0%}" if confidence is not None else ""

    st.markdown(
        f"**:{color}[{action_type.upper()} {symbol}]** — {reason}  \n"
        f"{badge}{conf_str}"
    )


def render_signal_layer_card(
    st: Any,
    layer_name: str,
    icon: str,
    signal: str,
    details: dict[str, str],
) -> None:
    """Render a signal layer card for signal breakdown tab."""
    lines = [f"**{icon} {layer_name}**  ", f"Signal: **{signal}**  "]
    for k, v in details.items():
        lines.append(f"{k}: {v}  ")
    st.markdown("\n".join(lines))
