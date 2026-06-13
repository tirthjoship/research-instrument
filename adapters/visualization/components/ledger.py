"""Evidence Ledger component — horizontal metadata strip above instrument panels.

Renders a monospace strip with labeled key-value segments, using the ri-ledger
design token namespace. No third-party imports required.
"""

from __future__ import annotations

import html as _html


def render_ledger(segments: list[tuple[str, str]]) -> str:
    """Return an HTML string for a monospace evidence ledger strip.

    Each segment is a (label, value) pair rendered as::

        LABEL <b>VALUE</b>

    The outer element carries the ``ri-ledger`` CSS class so callers can inject
    it via ``st.markdown(..., unsafe_allow_html=True)``.

    Args:
        segments: Ordered list of (label, value) pairs. ``value`` is data and is
            escaped with :func:`html.escape`; ``label`` may carry trusted markup
            (e.g. a :func:`tooltip` span) and is inserted as-is.

    Returns:
        An HTML ``<div class="ri-ledger">`` string.
    """
    parts: list[str] = []
    for label, value in segments:
        safe_value = _html.escape(value)
        parts.append(f'<span class="ri-seg">{label} <b>{safe_value}</b></span>')
    inner = "\n".join(parts)
    return f'<div class="ri-ledger">\n{inner}\n</div>'
