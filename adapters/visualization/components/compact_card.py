"""Compact opportunity card HTML component.

Pure functions returning HTML strings for use with st.markdown(..., unsafe_allow_html=True).
"""

from __future__ import annotations

from datetime import datetime

from domain.conviction import ActionType, FreshnessLevel, OpportunityCard

_ACTION_BADGE_CSS: dict[ActionType, str] = {
    ActionType.BUY: "badge-buy",
    ActionType.SELL: "badge-sell",
    ActionType.WATCH: "badge-watch",
    ActionType.HOLD: "badge-hold",
}

_FRESHNESS_DOT_CSS: dict[FreshnessLevel, str] = {
    FreshnessLevel.FRESH: "badge-fresh",
    FreshnessLevel.RECENT: "badge-recent",
    FreshnessLevel.STALE: "badge-stale",
}


def _hold_duration_text(sub_scores: dict[str, float]) -> str:
    """Derive a hold duration hint from sub-score magnitudes.

    Uses sentiment + technical scores to categorise as short/medium/position hold.
    """
    sentiment = sub_scores.get("sentiment", 0.0)
    technical = sub_scores.get("technical", 0.0)
    avg = (sentiment + technical) / 2 if (sentiment or technical) else 0.0
    if avg >= 0.75:
        return "Hold until flip"
    elif avg >= 0.5:
        return "Position hold (5-10d)"
    elif avg >= 0.3:
        return "Short hold (2-3d)"
    else:
        return "Monitor daily"


def _sub_score_bars_html(sub_scores: dict[str, float]) -> str:
    """Render small horizontal bars for each sub-score (0-1 scale)."""
    _COLORS: dict[str, str] = {
        "sentiment": "#7C3AED",
        "technical": "#2563EB",
        "smart_money": "#059669",
        "fundamental": "#D97706",
        "event": "#EA580C",
    }
    bars = ""
    for key, val in sub_scores.items():
        color = _COLORS.get(key, "#94A3B8")
        pct = max(0, min(100, int(val * 100)))
        label = key.replace("_", " ").title()
        bars += (
            f'<div style="display:flex;align-items:center;gap:6px;margin-bottom:3px;">'
            f'<span style="font-size:11px;color:#94A3B8;width:80px;flex-shrink:0;">{label}</span>'
            f'<div style="flex:1;height:4px;background:#E5E7EB;border-radius:2px;overflow:hidden;">'
            f'<div style="width:{pct}%;height:4px;background:{color};border-radius:2px;"></div>'
            f"</div>"
            f'<span style="font-size:11px;color:#6B7280;width:30px;text-align:right;">{val:.0%}</span>'
            f"</div>"
        )
    return bars


def render_compact_card_html(card: OpportunityCard, now: datetime) -> str:
    """Return compact single-row HTML for an OpportunityCard.

    Layout:
      Row 1: ticker | conviction bar | score | action badge | freshness dot | hold duration
      Row 2: sub-score breakdown bars
      Row 3: alert_summary (one line)
      Row 4: abbreviated risks — first 2, joined by " · "
      Row 5: "Analyze" link text

    CSS card class is opp-card plus one of:
      opp-card-high (conviction >= 7), opp-card-mid (4-6), opp-card-low (< 4).
    """
    # Conviction tier CSS class
    if card.conviction >= 7:
        tier_class = "opp-card-high"
    elif card.conviction >= 4:
        tier_class = "opp-card-mid"
    else:
        tier_class = "opp-card-low"

    # Conviction bar fill (score is 1–10, render as 10%-100% width)
    bar_pct = int(card.conviction * 10)
    bar_color = (
        "#059669"
        if card.conviction >= 7
        else "#D97706" if card.conviction >= 4 else "#DC2626"
    )

    # Action badge
    action_css = _ACTION_BADGE_CSS.get(card.action, "badge-hold")

    # Freshness
    freshness = card.conviction_score.freshness_level(now)
    freshness_css = _FRESHNESS_DOT_CSS[freshness]
    freshness_label = freshness.value.capitalize()

    # Abbreviated risks (first 2, joined by " · ")
    risk_abbrev = " · ".join(card.risks[:2]) if card.risks else ""

    # Hold duration derived from sub-scores
    sub_scores = card.conviction_score.sub_scores
    hold_text = _hold_duration_text(sub_scores)

    # Sub-score bars
    sub_bars_html = _sub_score_bars_html(sub_scores) if sub_scores else ""

    return (
        f'<div class="opp-card {tier_class}">'
        # Row 1: ticker + conviction bar + score + badge + freshness + hold
        f'<div style="display:flex; align-items:center; gap:0.75rem; flex-wrap:wrap;">'
        f"<span style=\"font-family:'DM Sans',sans-serif; font-size:18px; font-weight:700;"
        f' color:#111827;">{card.ticker}</span>'
        # Conviction bar
        f'<div style="flex:1; min-width:60px; max-width:120px; height:6px;'
        f' background:#E5E7EB; border-radius:3px; overflow:hidden;">'
        f'<div class="conviction-fill" style="width:{bar_pct}%; height:6px;'
        f' background:{bar_color}; border-radius:3px;"></div>'
        f"</div>"
        # Score
        f"<span style=\"font-family:'JetBrains Mono',monospace; font-size:13px;"
        f' color:#374151;">{card.conviction:.1f}/10</span>'
        # Action badge
        f'<span class="badge {action_css}">{card.action.value}</span>'
        # Freshness dot + label
        f'<span class="status-dot {freshness_css}"></span>'
        f'<span style="font-size:12px; color:#6B7280;">{freshness_label}</span>'
        # Hold duration
        f'<span style="margin-left:auto; font-size:12px; color:#64748B; '
        f'font-style:italic;">{hold_text}</span>'
        f"</div>"
        # Row 2: sub-score bars
        + (
            f'<div style="margin-top:8px; padding:6px 0;">{sub_bars_html}</div>'
            if sub_bars_html
            else ""
        )
        # Row 3: alert summary
        + f'<div style="font-size:13px; color:#374151; margin-top:6px;">'
        f"{card.alert_summary}"
        f"</div>"
        # Row 4: abbreviated risks
        f'<div style="font-size:12px; color:#9CA3AF; margin-top:4px;">'
        f"{risk_abbrev}"
        f"</div>"
        # Row 5: analyze link
        f'<div style="margin-top:8px; font-size:12px;">'
        f'<span style="color:#2563EB; cursor:pointer; font-weight:500;">Analyze {card.ticker} &rarr;</span>'
        f"</div>"
        f"</div>"
    )
