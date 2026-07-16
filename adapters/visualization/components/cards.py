"""Reusable SWST-style HTML card components — no Streamlit dependency."""

from __future__ import annotations

from typing import Literal

from adapters.visualization.components.currency import (
    currency_for_ticker,
    currency_symbol,
)


def tooltip(text: str, help_text: str) -> str:
    """Wrap text with a hover tooltip icon."""
    return (
        f'<span class="tooltip-container">{text}'
        f'<span class="tooltip-icon">?</span>'
        f'<span class="tooltip-text">{help_text}</span>'
        f"</span>"
    )


def criteria_card(title: str, score: int, max_score: int, summary: str) -> str:
    """Render a criteria scoring card with dot indicators.

    Args:
        title: Card heading (e.g. "Valuation Score").
        score: Number of filled dots.
        max_score: Total dot count.
        summary: Explanatory text shown below the score row.

    Returns:
        HTML string with ws-card wrapper.
    """
    filled_dot = '<span style="color:#16A34A; font-size:14px;">&#9679;</span>'
    empty_dot = '<span style="color:#D1D5DB; font-size:14px;">&#9675;</span>'
    dots = filled_dot * score + empty_dot * (max_score - score)

    return (
        f'<div class="ws-card">'
        f'<div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:8px;">'
        f"<span style=\"font-family:'DM Sans', sans-serif; font-size:15px; font-weight:600; color:#1A202C;\">"
        f"{title}</span>"
        f'<span style="display:flex; gap:3px; align-items:center;">'
        f"<span style=\"font-family:'DM Sans', sans-serif; font-size:13px; font-weight:600; color:#64748B; margin-right:6px;\">"
        f"{score}/{max_score}</span>"
        f"{dots}"
        f"</span>"
        f"</div>"
        f"<p style=\"font-family:'Inter', sans-serif; font-size:13px; color:#64748B; margin:0; line-height:1.5;\">"
        f"{summary}</p>"
        f"</div>"
    )


def verdict_bullet(status: Literal["pass", "warn", "fail"], text: str) -> str:
    """Render a verdict bullet with colored icon.

    Args:
        status: One of "pass", "warn", "fail".
        text: Verdict description.

    Returns:
        HTML string with flex row icon + text.
    """
    _MAP: dict[str, tuple[str, str]] = {
        "pass": ("#16A34A", "&#10003;"),
        "warn": ("#F59E0B", "&#9888;"),
        "fail": ("#DC2626", "&#10007;"),
    }
    color, icon = _MAP.get(status, ("#64748B", "&#9679;"))
    return (
        f'<div style="display:flex; align-items:flex-start; gap:8px; margin-bottom:6px;">'
        f'<span style="color:{color}; font-size:15px; line-height:1.4; flex-shrink:0;">{icon}</span>'
        f"<span style=\"font-family:'Inter', sans-serif; font-size:14px; color:#1A202C; line-height:1.5;\">{text}</span>"
        f"</div>"
    )


def metric_kpi(
    label: str, value: str, context: str = "", color: str = "#0F172A"
) -> str:
    """Render a centered KPI metric block.

    Args:
        label: Uppercase label above the value.
        value: Primary display number/string (JetBrains Mono, 24px).
        context: Optional secondary text below the value.
        color: Hex color for the value text.

    Returns:
        HTML string with centered layout.
    """
    context_html = (
        f"<div style=\"font-family:'Inter', sans-serif; font-size:12px; color:#64748B; margin-top:4px;\">"
        f"{context}</div>"
        if context
        else ""
    )
    return (
        f'<div style="text-align:center; padding:12px 8px;">'
        f"<div style=\"font-family:'DM Sans', sans-serif; font-size:11px; font-weight:600;"
        f' color:#94A3B8; text-transform:uppercase; letter-spacing:0.8px; margin-bottom:6px;">'
        f"{label}</div>"
        f"<div style=\"font-family:'JetBrains Mono', monospace; font-size:24px; font-weight:500;"
        f' color:{color}; letter-spacing:-0.5px; line-height:1.2;">'
        f"{value}</div>"
        f"{context_html}"
        f"</div>"
    )


def price_range_bar(
    current: float,
    low: float,
    high: float,
    target: float | None = None,
    ticker: str = "",
) -> str:
    """Render a horizontal price range bar.

    Args:
        current: Current price shown as a blue circle marker.
        low: 52-week (or range) low — displayed at left.
        high: 52-week (or range) high — displayed at right.
        target: Optional analyst price target shown as a purple marker.
        ticker: Ticker whose market determines the currency symbol shown
            (defaults to USD "$" when omitted, preserving prior behavior).

    Returns:
        HTML string with inline SVG-free CSS bar.
    """
    sym = currency_symbol(currency_for_ticker(ticker))
    span = high - low if high != low else 1.0
    current_pct = max(0.0, min(100.0, (current - low) / span * 100))

    target_html = ""
    if target is not None:
        target_pct = max(0.0, min(100.0, (target - low) / span * 100))
        target_html = (
            f'<div style="position:absolute; left:{target_pct:.1f}%; top:-18px;'
            f" transform:translateX(-50%); font-family:'JetBrains Mono', monospace;"
            f' font-size:11px; color:#7C3AED; font-weight:600; white-space:nowrap;">'
            f"{sym}{target:.2f}</div>"
            f'<div style="position:absolute; left:{target_pct:.1f}%; top:0; bottom:0;'
            f' transform:translateX(-50%); width:2px; background:#7C3AED; border-radius:1px;"></div>'
        )

    return (
        f'<div style="padding:20px 0 8px 0;">'
        f'<div style="position:relative; height:8px; background:#E2E8F0; border-radius:999px; margin:24px 0 24px 0;">'
        # Fill bar from left to current position
        f'<div style="position:absolute; left:0; top:0; bottom:0; width:{current_pct:.1f}%;'
        f' background:linear-gradient(90deg, #BFDBFE 0%, #2563EB 100%); border-radius:999px;"></div>'
        # Target marker (if any)
        f"{target_html}"
        # Current price label above
        f'<div style="position:absolute; left:{current_pct:.1f}%; top:-22px; transform:translateX(-50%);'
        f" font-family:'JetBrains Mono', monospace; font-size:12px; color:#2563EB; font-weight:600;"
        f' white-space:nowrap;">{sym}{current:.2f}</div>'
        # Current price dot
        f'<div style="position:absolute; left:{current_pct:.1f}%; top:50%; transform:translate(-50%, -50%);'
        f" width:14px; height:14px; background:#2563EB; border-radius:50%; border:2px solid #FFFFFF;"
        f' box-shadow:0 0 0 2px #2563EB;"></div>'
        f"</div>"
        # Low / high labels
        f'<div style="display:flex; justify-content:space-between;">'
        f"<span style=\"font-family:'Inter', sans-serif; font-size:11px; color:#94A3B8;\">{sym}{low:.2f}</span>"
        f"<span style=\"font-family:'Inter', sans-serif; font-size:11px; color:#94A3B8;\">{sym}{high:.2f}</span>"
        f"</div>"
        f"</div>"
    )


def mini_sparkline(
    prices: list[float],
    width: int = 120,
    height: int = 30,
    color: str = "#2563EB",
) -> str:
    """Render an inline SVG sparkline polyline.

    Args:
        prices: List of price values (time-ordered).
        width: SVG width in pixels.
        height: SVG height in pixels.
        color: Stroke color override (ignored — auto-set by direction).

    Returns:
        SVG string, or "—" for empty/single-element lists.
    """
    if len(prices) <= 1:
        return "\u2014"

    line_color = "#16A34A" if prices[-1] >= prices[0] else "#DC2626"

    price_min = min(prices)
    price_max = max(prices)
    span = price_max - price_min if price_max != price_min else 1.0

    n = len(prices)
    padding = 2

    def _x(i: int) -> float:
        return padding + (i / (n - 1)) * (width - 2 * padding)

    def _y(p: float) -> float:
        # Inverted: higher price = lower y
        return padding + (1 - (p - price_min) / span) * (height - 2 * padding)

    points = " ".join(f"{_x(i):.1f},{_y(p):.1f}" for i, p in enumerate(prices))

    return (
        f'<svg width="{width}" height="{height}" xmlns="http://www.w3.org/2000/svg"'
        f' style="display:inline-block; vertical-align:middle;">'
        f'<polyline points="{points}" fill="none" stroke="{line_color}"'
        f' stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"/>'
        f"</svg>"
    )


def loading_stepper_html(steps: list[str], current: int) -> str:
    """Render a progress stepper with gradient bar.

    Args:
        steps: List of step labels (in order).
        current: Zero-based index of the active step.

    Returns:
        HTML string with progress bar and step list.
    """
    pct = (current + 1) / len(steps) * 100 if steps else 0.0

    step_items: list[str] = []
    for i, label in enumerate(steps):
        if i < current:
            # Completed
            icon = '<span style="color:#16A34A; font-size:14px; flex-shrink:0;">&#10003;</span>'
            text_color = "#64748B"
        elif i == current:
            # Active
            icon = (
                '<span style="display:inline-block; width:10px; height:10px;'
                ' background:#2563EB; border-radius:50%; flex-shrink:0; margin-top:3px;"></span>'
            )
            text_color = "#1A202C"
        else:
            # Future
            icon = (
                '<span style="display:inline-block; width:10px; height:10px;'
                ' border:2px solid #D1D5DB; border-radius:50%; flex-shrink:0; margin-top:3px;"></span>'
            )
            text_color = "#94A3B8"

        step_items.append(
            f'<div style="display:flex; align-items:flex-start; gap:10px; margin-bottom:8px;">'
            f"{icon}"
            f"<span style=\"font-family:'Inter', sans-serif; font-size:13px; color:{text_color};\">"
            f"{label}</span>"
            f"</div>"
        )

    steps_html = "".join(step_items)

    return (
        f'<div style="padding:8px 0;">'
        # Progress bar
        f'<div style="background:#E2E8F0; border-radius:999px; height:6px; margin-bottom:16px; overflow:hidden;">'
        f'<div style="height:6px; border-radius:999px; width:{pct:.0f}%;'
        f" background:linear-gradient(90deg, #2563EB 0%, #7C3AED 100%);"
        f' transition:width 0.4s ease;"></div>'
        f"</div>"
        # Step list
        f"{steps_html}"
        f"</div>"
    )
