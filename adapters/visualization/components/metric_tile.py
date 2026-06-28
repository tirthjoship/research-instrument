"""Tone-bordered metric tile for vitals + 6-metric strips. viz/info are optional."""

from __future__ import annotations

import html as _html

from adapters.visualization.components.info_tip import render_info

_TONES = {"amber", "green", "grey", "petrol", "crimson"}


def render_metric_tile(
    label: str,
    value: str,
    *,
    sub: str | None = None,
    tone: str = "grey",
    viz: str | None = None,
    info_meaning: str | None = None,
    info_basis: str | None = None,
) -> str:
    if tone not in _TONES:
        raise ValueError(f"tone must be one of {_TONES}, got {tone!r}")
    info = render_info(info_meaning, info_basis) if info_meaning else ""
    sub_html = f'<div class="sub">{_html.escape(sub)}</div>' if sub else ""
    viz_html = viz or ""
    return (
        f'<div class="sa-tile t-{tone}">'
        f'<div class="lab">{_html.escape(label)} {info}</div>'
        f'<div class="num">{_html.escape(value)}</div>'
        f"{viz_html}{sub_html}"
        "</div>"
    )
