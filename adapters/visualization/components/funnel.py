"""Screener funnel exhibit — stepped count-down from universe to cleared names.

Renders a horizontal funnel strip: Universe N → … → cleared M.
When the final stage has a count of 0 the last step uses the amber tone
(abstention signal — the discipline is working, not failing).
No directional language. No fabricated intermediate counts.
"""

from __future__ import annotations


def render_funnel(stages: list[tuple[str, int]]) -> str:
    """Return an HTML string for a stepped screener funnel.

    Each element of *stages* is a ``(label, count)`` pair where *label* is
    treated as trusted markup (may carry a tooltip span) and *count* is an
    integer rendered directly.

    The final stage uses amber styling when its count is 0 (no names
    passed all gates this week).  All other steps use the neutral ink tone.

    Args:
        stages: Ordered list of ``(label, count)`` pairs from broadest to
            narrowest.  At least one pair is required.

    Returns:
        An HTML ``<div class="ri-funnel">`` string suitable for injection via
        ``st.markdown(..., unsafe_allow_html=True)``.
    """
    if not stages:
        return '<div class="ri-funnel"></div>'

    step_parts: list[str] = []
    last_idx = len(stages) - 1

    for i, (label, count) in enumerate(stages):
        is_last = i == last_idx
        tone_class = "ri-funnel-step--amber" if (is_last and count == 0) else ""

        step_html = (
            f'<div class="ri-funnel-step {tone_class}">'
            f'<span class="ri-funnel-label">{label}</span>'
            f'<span class="ri-funnel-count">{count}</span>'
            f"</div>"
        )
        step_parts.append(step_html)

        if not is_last:
            step_parts.append('<span class="ri-funnel-arrow">&#8594;</span>')

    inner = "\n".join(step_parts)
    return f'<div class="ri-funnel">\n{inner}\n</div>'
