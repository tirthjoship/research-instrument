"""Dashboard formatters — grade colors, direction icons, urgency badges, number formatting."""

from __future__ import annotations

from datetime import datetime

from domain.conviction import ActionType, FreshnessLevel

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


_GRADE_DISPLAY_NAMES: dict[str, str] = {
    "strong_buy": "Strong Buy",
    "buy": "Buy",
    "hold": "Hold",
    "may_sell": "May Sell",
    "immediate_sell": "Immediate Sell",
    # Fit-verdict evidence grades (domain/fit.py)
    "STRONG": "Strong",
    "MODERATE": "Moderate",
    "WEAK": "Weak",
    "UNKNOWN": "Unknown",
}

_GRADE_CSS_CLASSES: dict[str, str] = {
    "strong_buy": "grade-strong-buy",
    "buy": "grade-buy",
    "hold": "grade-hold",
    "may_sell": "grade-may-sell",
    "immediate_sell": "grade-immediate-sell",
    # Fit-verdict evidence grades reuse existing color classes
    "STRONG": "grade-strong-buy",
    "MODERATE": "grade-hold",
    "WEAK": "grade-may-sell",
    "UNKNOWN": "grade-hold",
}


def grade_display_name(grade_value: str) -> str:
    """Convert enum value 'strong_buy' → 'Strong Buy'."""
    if grade_value in _GRADE_DISPLAY_NAMES:
        return _GRADE_DISPLAY_NAMES[grade_value]
    if grade_value in _GRADE_DISPLAY_NAMES.values():
        return grade_value
    return grade_value.replace("_", " ").title()


def grade_badge_html(grade_value: str) -> str:
    """Return HTML for a colored grade badge."""
    display = grade_display_name(grade_value)
    css_class = _GRADE_CSS_CLASSES.get(grade_value, "")
    return f'<span class="grade-badge {css_class}">{display}</span>'


def status_pill_html(status: str, label: str) -> str:
    """Return HTML for a colored status pill."""
    css_class = f"pill-{status}"
    return f'<span class="status-pill {css_class}">{label}</span>'


def signal_pill_html(direction: str) -> str:
    """Return HTML for a signal direction pill."""
    css_map = {
        "bullish": "signal-bullish",
        "bearish": "signal-bearish",
        "neutral": "signal-neutral",
    }
    css_class = css_map.get(direction.lower(), "signal-neutral")
    display = direction.upper()
    return f'<span class="signal-pill {css_class}">{display}</span>'


def confidence_bar_html(confidence: float) -> str:
    """Return HTML for a mini confidence progress bar."""
    pct_val = max(0, min(100, int(confidence * 100)))
    color = "#00C853" if pct_val >= 70 else "#FFD600" if pct_val >= 40 else "#FF1744"
    return (
        f'<div class="confidence-bar-bg">'
        f'<div class="confidence-bar-fill" style="width: {pct_val}%; background: {color};"></div>'
        f"</div>"
        f'<span style="font-size: 12px; color: #6B7280;">{pct_val}%</span>'
    )


def freshness_status_html(timestamp: datetime | None) -> str:
    """Return HTML status pill for data freshness."""
    if timestamp is None:
        return status_pill_html("critical", "Never run")

    hours_ago = (datetime.now() - timestamp).total_seconds() / 3600

    if hours_ago < 6:
        label = f"{hours_ago:.0f}h ago" if hours_ago >= 1 else "just now"
        return status_pill_html("fresh", label)
    elif hours_ago < 24:
        return status_pill_html("stale", f"{hours_ago:.0f}h ago")
    elif hours_ago < 72:
        return status_pill_html("warning", f"{hours_ago / 24:.0f}d ago")
    else:
        return status_pill_html("critical", f"{hours_ago / 24:.0f}d ago")


def urgency_pill_html(urgency: str) -> str:
    """Return HTML pill for urgency level — no emoji."""
    mapping: dict[str, tuple[str, str]] = {
        "immediate": ("pill-urgent", "URGENT"),
        "this_week": ("pill-this-week", "THIS WEEK"),
        "watch": ("pill-watch-priority", "WATCH"),
    }
    css_class, label = mapping.get(urgency, ("pill-watch-priority", "WATCH"))
    return f'<span class="status-pill {css_class}">{label}</span>'


def conviction_badge_html(score: float) -> str:
    """Return colored HTML badge for a conviction score.

    Green >= 7, amber >= 4, red < 4. Formatted as "8.5/10" in a rounded pill.
    """
    if score >= 7:
        bg, color = "#DCFCE7", "#166534"
    elif score >= 4:
        bg, color = "#FEF9C3", "#854D0E"
    else:
        bg, color = "#FEE2E2", "#991B1B"
    return (
        f'<span style="display:inline-block; background:{bg}; color:{color};'
        f' padding:3px 12px; border-radius:12px; font-size:13px; font-weight:700;">'
        f"{score:.1f}/10</span>"
    )


def action_badge_html(action: ActionType) -> str:
    """Return colored HTML badge for an ActionType.

    BUY=green, SELL=red, WATCH=amber, HOLD=gray.
    """
    mapping: dict[ActionType, tuple[str, str]] = {
        ActionType.BUY: ("#DCFCE7", "#166534"),
        ActionType.SELL: ("#FEE2E2", "#991B1B"),
        ActionType.WATCH: ("#FEF9C3", "#854D0E"),
        ActionType.HOLD: ("#F3F4F6", "#4B5563"),
    }
    bg, color = mapping.get(action, ("#F3F4F6", "#4B5563"))
    return (
        f'<span style="display:inline-block; background:{bg}; color:{color};'
        f' padding:3px 12px; border-radius:12px; font-size:13px; font-weight:700;">'
        f"{action.value}</span>"
    )


def freshness_indicator_html(level: FreshnessLevel) -> str:
    """Return "● Fresh" / "● Recent" / "● Stale" with a colored dot."""
    mapping: dict[FreshnessLevel, tuple[str, str]] = {
        FreshnessLevel.FRESH: ("#059669", "Fresh"),
        FreshnessLevel.RECENT: ("#D97706", "Recent"),
        FreshnessLevel.STALE: ("#DC2626", "Stale"),
    }
    dot_color, label = mapping[level]
    return (
        f'<span style="color:{dot_color}; font-size:14px;">●</span>'
        f'<span style="font-size:13px; color:#6B7280; margin-left:4px;">{label}</span>'
    )


def freshness_dot_html(timestamp: datetime | None) -> str:
    """Return HTML freshness indicator with colored dot — no emoji."""
    if timestamp is None:
        return '<span class="freshness-dot dot-critical"></span>Never run'

    hours_ago = (datetime.now() - timestamp).total_seconds() / 3600

    if hours_ago < 6:
        label = f"{hours_ago:.0f}h ago" if hours_ago >= 1 else "just now"
        return f'<span class="freshness-dot dot-fresh"></span>{label}'
    elif hours_ago < 24:
        return f'<span class="freshness-dot dot-stale"></span>{hours_ago:.0f}h ago'
    elif hours_ago < 72:
        return (
            f'<span class="freshness-dot dot-warning"></span>{hours_ago / 24:.0f}d ago'
        )
    else:
        return (
            f'<span class="freshness-dot dot-critical"></span>{hours_ago / 24:.0f}d ago'
        )
