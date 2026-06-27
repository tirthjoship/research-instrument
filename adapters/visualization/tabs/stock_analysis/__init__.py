"""Stock analysis tab package."""

from adapters.visualization.tabs.stock_analysis.compose import (
    _SECTION_LABELS,
    _ensure_fit_cached,
    _render_decision_lead_html,
    render,
    select_case_summarizer,
)
from adapters.visualization.tabs.stock_analysis.corroboration_section import (
    render_corroboration_section,
)
from adapters.visualization.tabs.stock_analysis.verdict_section import (
    _SEVERITY_CLASS,
    _convergence_badge_html,
    _render_analyst_panel,
    _render_fit_card,
    _render_news_context,
    _render_peer_percentiles,
    _render_verdict,
    _snowflake_axes,
)

__all__ = [
    "render",
    "_SECTION_LABELS",
    "_ensure_fit_cached",
    "_render_decision_lead_html",
    "select_case_summarizer",
    "render_corroboration_section",
    "_SEVERITY_CLASS",
    "_convergence_badge_html",
    "_render_analyst_panel",
    "_render_fit_card",
    "_render_news_context",
    "_render_peer_percentiles",
    "_render_verdict",
    "_snowflake_axes",
]
