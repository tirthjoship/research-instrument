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


def render_compact_card_html(card: OpportunityCard, now: datetime) -> str:
    """Return compact single-row HTML for an OpportunityCard.

    Layout:
      Row 1: ticker | conviction bar | score | action badge | freshness dot
      Row 2: alert_summary (one line)
      Row 3: abbreviated risks — first 2, joined by " · "

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

    return (
        f'<div class="opp-card {tier_class}">'
        # Row 1: ticker + conviction bar + score + badge + freshness
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
        f"</div>"
        # Row 2: alert summary
        f'<div style="font-size:13px; color:#374151; margin-top:6px;">'
        f"{card.alert_summary}"
        f"</div>"
        # Row 3: abbreviated risks
        f'<div style="font-size:12px; color:#9CA3AF; margin-top:4px;">'
        f"{risk_abbrev}"
        f"</div>"
        f"</div>"
    )
