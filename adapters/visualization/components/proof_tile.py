"""Proof-tile component — anti-KPI card for falsified-hypothesis evidence display.

Each tile shows a metric label, a large number, an optional rubber-stamp badge,
and an optional sub-caption. The stamp communicates test outcome (e.g. FALSIFIED,
INCONCLUSIVE, REPLICATED) rather than any directional forecast.

No Streamlit or third-party imports are needed; the module is pure HTML-string
returning so it can be unit-tested without a browser environment.
"""

from __future__ import annotations

import html as _html

_VALID_TONES: frozenset[str] = frozenset({"crimson", "amber", "green", "muted"})


def render_tile(
    label: str,
    number: str,
    stamp: str | None = None,
    tone: str = "muted",
    sub: str | None = None,
) -> str:
    """Return an HTML string for a proof-tile card.

    The card uses a 4px left-border color rule driven by *tone* and, when
    *stamp* is provided, places a rotated rubber-stamp badge in the top-right
    corner.

    Args:
        label: Short metric name shown in monospace uppercase caps. May carry
            trusted markup (e.g. a :func:`tooltip` span); inserted as-is.
        number: Primary numeric value displayed large (Fraunces typeface).
        stamp: Optional outcome badge text (e.g. ``"FALSIFIED"``). Rendered
            only when not ``None`` or empty.
        tone: One of ``"crimson"``, ``"amber"``, ``"green"``, ``"muted"``.
            Unknown values are normalised to ``"muted"``.
        sub: Optional sub-caption rendered below the number in body text.

    Returns:
        An HTML ``<div class="ri-tile t-{tone}">`` string.
    """
    safe_tone = tone if tone in _VALID_TONES else "muted"

    safe_number = _html.escape(number)

    stamp_html = ""
    if stamp:
        safe_stamp = _html.escape(stamp)
        stamp_html = f'<span class="ri-stamp">{safe_stamp}</span>\n'

    sub_html = ""
    if sub:
        safe_sub = _html.escape(sub)
        sub_html = f'<p class="ri-sub">{safe_sub}</p>\n'

    return (
        f'<div class="ri-tile t-{safe_tone}">\n'
        f"{stamp_html}"
        f'<span class="ri-lab">{label}</span>\n'
        f'<p class="ri-num">{safe_number}</p>\n'
        f"{sub_html}"
        f"</div>"
    )
