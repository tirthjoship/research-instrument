"""Dashboard formatters — grade colors, direction icons, urgency badges, number formatting."""

from __future__ import annotations

from datetime import datetime

_GRADE_COLORS: dict[str, str] = {
    "Strong Buy": "#00C853",
    "Buy": "#69F0AE",
    "Hold": "#FFD600",
    "May Sell": "#FF9100",
    "Immediate Sell": "#FF1744",
}

_DIRECTION_ICONS: dict[str, str] = {
    "bullish": "🟢",
    "bearish": "🔴",
    "neutral": "⚪",
}


def grade_color(grade: str) -> str:
    """Return hex color for a recommendation grade."""
    return _GRADE_COLORS.get(grade, "#9E9E9E")


def direction_icon(direction: str) -> str:
    """Return emoji icon for a signal direction."""
    return _DIRECTION_ICONS.get(direction, "⚪")


def urgency_badge(urgency: str) -> str:
    """Return formatted urgency badge string."""
    badges: dict[str, str] = {
        "immediate": "🔴 IMMEDIATE",
        "this_week": "🟡 THIS WEEK",
        "watch": "⚪ WATCH",
    }
    return badges.get(urgency, "⚪ WATCH")


def pct(value: float | None) -> str:
    """Format a decimal as a percentage string with sign."""
    if value is None:
        return "N/A"
    sign = "+" if value >= 0 else ""
    return f"{sign}{value * 100:.2f}%"


def freshness_status(timestamp: datetime | None) -> tuple[str, str]:
    """Return (icon, label) for data freshness.

    Thresholds: <6h = ✅, 6-24h = 🟡, 24-72h = ⚠️, >72h = ❌.
    """
    if timestamp is None:
        return "❌", "Never run"

    hours_ago = (datetime.now() - timestamp).total_seconds() / 3600

    if hours_ago < 6:
        label = f"{hours_ago:.0f}h ago" if hours_ago >= 1 else "just now"
        return "✅", label
    elif hours_ago < 24:
        return "🟡", f"{hours_ago:.0f}h ago"
    elif hours_ago < 72:
        days = hours_ago / 24
        return "⚠️", f"{days:.0f}d ago"
    else:
        days = hours_ago / 24
        return "❌", f"{days:.0f}d ago"
