"""Measured-colour status chip: colour always carries a stated rule (anti-false-claim)."""

from __future__ import annotations

import html as _html

from adapters.visualization.components.info_tip import render_info

_TONES = {"amber", "green", "grey", "petrol", "crimson"}


def render_status_chip(label: str, value: str, tone: str, rule: str) -> str:
    if tone not in _TONES:
        raise ValueError(f"tone must be one of {_TONES}, got {tone!r}")
    if not rule or not rule.strip():
        raise ValueError("rule is required: colour must state its measurement basis")
    info = render_info(rule)
    return (
        f'<span class="sa-chip t-{tone}">'
        f"{_html.escape(label)} <b>{_html.escape(value)}</b>"
        f"{info}"
        "</span>"
    )
