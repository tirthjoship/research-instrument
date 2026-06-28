"""Pure-SVG category-coded snowflake radar (spec D5/D7): rings + median baseline + value polygon."""

from __future__ import annotations

import html as _html
import math
from dataclasses import dataclass


@dataclass(frozen=True)
class RadarAxis:
    label: str
    value: float
    colour: str


def _point(
    cx: float, cy: float, radius: float, angle_deg: float
) -> tuple[float, float]:
    a = math.radians(angle_deg)
    return (cx + radius * math.cos(a), cy + radius * math.sin(a))


def _polygon(
    points: list[tuple[float, float]],
    *,
    fill: str,
    stroke: str,
    width: float = 1.0,
    dash: str | None = None,
) -> str:
    pts = " ".join(f"{x:.2f},{y:.2f}" for x, y in points)
    dash_attr = f' stroke-dasharray="{dash}"' if dash else ""
    return f'<polygon points="{pts}" fill="{fill}" stroke="{stroke}" stroke-width="{width}"{dash_attr}/>'


def build_radar_svg(
    axes: list[RadarAxis], *, size: int = 260, median: float = 50.0
) -> str:
    if len(axes) < 3:
        raise ValueError("radar needs at least 3 axes")
    n = len(axes)
    cx = size / 2
    cy = size * 0.385  # leave room for bottom label
    r_max = size * 0.27
    angles = [-90 + i * (360 / n) for i in range(n)]

    parts: list[str] = []
    # grid rings at 25/50/75/100
    for frac in (0.25, 0.5, 0.75, 1.0):
        ring = [_point(cx, cy, r_max * frac, a) for a in angles]
        parts.append(_polygon(ring, fill="none", stroke="#e6e6e6"))
    # spokes
    spokes = "".join(
        f'<line x1="{cx:.2f}" y1="{cy:.2f}" x2="{x:.2f}" y2="{y:.2f}"/>'
        for x, y in (_point(cx, cy, r_max, a) for a in angles)
    )
    parts.append(f'<g stroke="#ededed">{spokes}</g>')
    # dashed median baseline
    med = [_point(cx, cy, r_max * (median / 100.0), a) for a in angles]
    parts.append(
        _polygon(
            med, fill="rgba(154,166,170,.05)", stroke="#9aa6aa", width=1.0, dash="3,3"
        )
    )
    # value polygon (petrol)
    vals = [
        _point(cx, cy, r_max * (max(0.0, min(100.0, ax.value)) / 100.0), a)
        for ax, a in zip(axes, angles)
    ]
    parts.append(
        _polygon(vals, fill="rgba(15,110,128,.13)", stroke="#0F6E80", width=1.6)
    )
    # category vertex dots
    for (x, y), ax in zip(vals, axes):
        parts.append(f'<circle cx="{x:.2f}" cy="{y:.2f}" r="3" fill="{ax.colour}"/>')
    # labels just outside the outer ring
    labels: list[str] = []
    for ax, a in zip(axes, angles):
        lx, ly = _point(cx, cy, r_max + 18, a)
        if abs(math.cos(math.radians(a))) < 0.3:
            anchor = "middle"
        elif math.cos(math.radians(a)) > 0:
            anchor = "start"
        else:
            anchor = "end"
        text = _html.escape(f"{ax.label} {int(round(ax.value))}")
        labels.append(
            f'<text x="{lx:.2f}" y="{ly:.2f}" text-anchor="{anchor}" '
            f'font-size="8.5" font-weight="700" fill="{ax.colour}">{text}</text>'
        )
    parts.append("<g>" + "".join(labels) + "</g>")
    body = "".join(parts)
    return (
        f'<svg width="100%" viewBox="0 0 {size} {int(size * 0.74)}" '
        f"style=\"font-family:'IBM Plex Mono',monospace\">{body}</svg>"
    )
