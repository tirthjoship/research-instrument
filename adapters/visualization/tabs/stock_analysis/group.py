"""Collapsed deep-dive group shell (spec D8): header + micro-tiles + (later) inner panels."""

from __future__ import annotations

import html as _html
from dataclasses import dataclass


@dataclass(frozen=True)
class MicroTile:
    label: str
    value: str
    colour: str
    pct: float | None = None  # 0-100 -> mini percentile bar (None = no bar)
    info: str = ""  # ⓘ tooltip HTML (render_info output); already escaped


def _micro_tile_html(t: MicroTile) -> str:
    e = _html.escape
    bar = ""
    if t.pct is not None:
        w = max(0.0, min(100.0, t.pct))
        bar = (
            '<span class="pb"><span class="pf" '
            f'style="width:{w:.0f}%;background:{e(t.colour)}"></span></span>'
        )
    return (
        '<span class="sa-gt">'
        f'<span class="d" style="background:{e(t.colour)}"></span>'
        f'<span class="col"><span class="gl">{e(t.label)}{t.info}</span>'
        f'<span class="gv">{e(t.value)}</span></span>{bar}</span>'
    )


def build_group_shell(
    *,
    anchor: str,
    name: str,
    grade: str,
    week_delta: str,
    micro_tiles: list[MicroTile],
    inner_html: str = "",
) -> str:
    e = _html.escape
    tiles = "".join(_micro_tile_html(t) for t in micro_tiles)
    week = f'<span class="sa-gweek">{e(week_delta)}</span>' if week_delta else ""
    inner = (
        f'<div class="ginner" style="border-top:1px solid var(--ri-line);padding:2px 15px 12px">{inner_html}</div>'
        if inner_html
        else ""
    )
    return (
        f'<details class="sa-group" id="{e(anchor)}"><summary>'
        '<div class="sa-ghead">'
        '<span class="sa-chev">▶</span>'
        f'<span class="sa-gname">{e(name)}</span>'
        f'<span class="sa-ggrade">GRADE {e(grade)}</span>'
        f"{week}</div>"
        f'<div style="display:grid;grid-template-columns:repeat(3,1fr);gap:9px;margin-top:10px">{tiles}</div>'
        "</summary>"
        f"{inner}</details>"
    )
