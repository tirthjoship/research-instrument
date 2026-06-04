"""Learning progress bar HTML component.

Pure functions returning HTML strings for use with st.markdown(..., unsafe_allow_html=True).
"""

from __future__ import annotations

_MILESTONE_THRESHOLD = 50


def _get_message(n_outcomes: int) -> str:
    """Return contextual message based on outcome count."""
    if n_outcomes == 0:
        return "Track your first trade"
    if n_outcomes < 10:
        more = 10 - n_outcomes
        return f"{n_outcomes} trade{'s' if n_outcomes > 1 else ''}, {more} more for first insights"
    if n_outcomes < _MILESTONE_THRESHOLD:
        return "Patterns are emerging"
    return "Reliable intelligence"


def _get_milestone_text(n_outcomes: int) -> str:
    """Return milestone text below the progress bar."""
    if n_outcomes == 0:
        return "No trades recorded yet"
    if n_outcomes < 10:
        return "Milestone: 10 trades → first signal insights"
    if n_outcomes < _MILESTONE_THRESHOLD:
        remaining = _MILESTONE_THRESHOLD - n_outcomes
        return f"{remaining} more trade{'s' if remaining > 1 else ''} to unlock reliable intelligence"
    return f"{n_outcomes} trades recorded — full learning mode active"


def render_learning_progress_html(n_outcomes: int) -> str:
    """Return HTML for the learning progress bar.

    Shows:
      - Contextual message based on trade count
      - Progress bar filled to n/50 × 100% (capped at 100%)
      - Milestone text below the bar

    CSS classes used: learning-progress, learning-progress-fill.

    Args:
        n_outcomes: Number of completed trade outcomes recorded.

    Returns:
        HTML string for the learning progress section.
    """
    fill_pct = min(100, int(n_outcomes / _MILESTONE_THRESHOLD * 100))
    bar_color = "#2563EB" if fill_pct < 100 else "#059669"

    message = _get_message(n_outcomes)
    milestone = _get_milestone_text(n_outcomes)

    return (
        f'<div class="learning-progress">'
        f'<div style="font-size:14px; font-weight:600; color:#111827; margin-bottom:6px;">'
        f"{message}"
        f"</div>"
        f'<div style="background:#E5E7EB; border-radius:4px; height:8px; overflow:hidden;">'
        f'<div class="learning-progress-fill"'
        f' style="width:{fill_pct}%; height:8px; background:{bar_color}; border-radius:4px;'
        f' transition:width 0.4s ease;"></div>'
        f"</div>"
        f'<div style="font-size:12px; color:#6B7280; margin-top:4px;">{milestone}</div>'
        f"</div>"
    )
