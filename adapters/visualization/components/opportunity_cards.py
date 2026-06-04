"""HTML renderers for OpportunityCard domain objects.

Pure functions — no Streamlit imports. Returns HTML strings for use with
st.markdown(..., unsafe_allow_html=True).
"""

from __future__ import annotations

from datetime import datetime

from adapters.visualization.components.formatters import (
    action_badge_html,
    conviction_badge_html,
    freshness_indicator_html,
)
from domain.conviction import OpportunityCard


def render_evidence_html(evidence: list[str]) -> str:
    """Return a styled <ul> list of evidence items."""
    if not evidence:
        return '<ul style="margin:0; padding-left:1.25rem; color:#374151;"></ul>'
    items_html = "".join(
        f'<li style="font-size:13px; color:#374151; margin-bottom:4px;">{item}</li>'
        for item in evidence
    )
    return (
        f'<ul style="margin:0; padding-left:1.25rem; list-style-type:disc;">'
        f"{items_html}</ul>"
    )


def render_risk_html(risks: list[str]) -> str:
    """Return an orange warning box with a 'What could go wrong' header."""
    items_html = "".join(
        f'<li style="font-size:13px; margin-bottom:3px;">{risk}</li>' for risk in risks
    )
    return (
        f'<div style="background:#FFEDD5; border:1px solid #FED7AA;'
        f" border-left:4px solid #EA580C; border-radius:8px;"
        f' padding:0.75rem 1rem; margin-top:0.75rem;">'
        f'<div style="font-size:13px; font-weight:600; color:#9A3412;'
        f' margin-bottom:6px;">What could go wrong</div>'
        f'<ul style="margin:0; padding-left:1.25rem; color:#92400E;">'
        f"{items_html}</ul></div>"
    )


def render_opportunity_card_html(card: OpportunityCard, now: datetime) -> str:
    """Return full HTML for an opportunity card.

    Layout (4 parts):
      1. Header — ticker, conviction badge, action badge, freshness indicator
      2. Alert summary — one-sentence headline
      3. Evidence list + suggestion box
      4. Risk warning box

    Left border is colored by conviction: green >= 7, amber >= 4, red < 4.
    """
    # Border color by conviction
    if card.conviction >= 7:
        border_color = "#00C853"
    elif card.conviction >= 4:
        border_color = "#FFD600"
    else:
        border_color = "#FF1744"

    freshness = card.conviction_score.freshness_level(now)

    conviction_html = conviction_badge_html(card.conviction)
    action_html = action_badge_html(card.action)
    freshness_html = freshness_indicator_html(freshness)

    evidence_html = render_evidence_html(card.evidence)
    risk_html = render_risk_html(card.risks)

    suggestion_html = (
        f'<div style="background:#EFF6FF; border:1px solid #BFDBFE;'
        f' border-radius:8px; padding:0.75rem 1rem; margin-top:0.75rem;">'
        f'<div style="font-size:13px; font-weight:600; color:#1E40AF;'
        f' margin-bottom:4px;">Suggested action</div>'
        f'<div style="font-size:13px; color:#1E3A8A;">{card.suggestion}</div>'
        f"</div>"
    )

    return (
        f'<div class="dashboard-card opportunity-card"'
        f' style="border-left:4px solid {border_color};">'
        # Header
        f'<div style="display:flex; justify-content:space-between;'
        f' align-items:center; margin-bottom:8px;">'
        f'<span style="font-size:18px; font-weight:700; color:#111827;">'
        f"{card.ticker}</span>"
        f'<span style="display:flex; gap:6px; align-items:center;">'
        f"{conviction_html}{action_html}{freshness_html}"
        f"</span></div>"
        # Alert summary
        f'<div style="font-size:14px; color:#374151; margin-bottom:10px;">'
        f"{card.alert_summary}</div>"
        # Evidence
        f'<div style="font-size:13px; font-weight:600; color:#111827;'
        f' margin-bottom:4px;">Supporting evidence</div>'
        f"{evidence_html}"
        # Suggestion
        f"{suggestion_html}"
        # Risk
        f"{risk_html}"
        f"</div>"
    )
