"""Working hover tooltip: plain meaning + optional measurement/source basis."""

from __future__ import annotations

import html as _html


def render_info(meaning: str, basis: str | None = None) -> str:
    safe_meaning = _html.escape(meaning)
    basis_html = (
        f'<span class="sa-tip-basis">{_html.escape(basis)}</span>' if basis else ""
    )
    return (
        '<span class="sa-tw">'
        '<span class="sa-info">i</span>'
        f'<span class="sa-tip">{safe_meaning}{basis_html}</span>'
        "</span>"
    )
