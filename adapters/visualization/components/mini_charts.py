"""Pure SVG/HTML mini-chart builders for the stock-analysis redesign."""

from __future__ import annotations

import html as _html


def sparkline(
    values: list[float], *, color: str = "#15803d", width: int = 80, height: int = 16
) -> str:
    if not values:
        return ""
    lo, hi = min(values), max(values)
    span = (hi - lo) or 1.0
    n = len(values)
    step = width / max(n - 1, 1)
    pts = []
    for i, v in enumerate(values):
        x = round(i * step, 2)
        y = round(height - 2 - ((v - lo) / span) * (height - 4), 2)
        pts.append(f"{x},{y}")
    return (
        f'<svg width="100%" height="{height}" viewBox="0 0 {width} {height}" '
        f'preserveAspectRatio="none" style="margin-top:6px">'
        f'<polyline points="{" ".join(pts)}" fill="none" stroke="{color}" stroke-width="1.5"/>'
        "</svg>"
    )


def percentile_bar(pct: float, *, color: str = "#0F6E80") -> str:
    p = max(0.0, min(100.0, float(pct)))
    return (
        '<div class="sa-pbar" style="height:5px;border-radius:3px;background:#e7ebec;'
        'position:relative;margin-top:6px">'
        f'<div style="position:absolute;left:0;top:0;bottom:0;border-radius:3px;'
        f'width:{p:.0f}%;background:{color}"></div>'
        f'<div style="position:absolute;top:-2px;left:{p:.0f}%;width:2px;height:9px;'
        f'background:{color}"></div>'
        f"<!--{p:.0f}--></div>"
    )


def range_bar(low: float, high: float, markers: list[tuple[float, str, str]]) -> str:
    span = (high - low) or 1.0
    mk = []
    for value, label, color in markers:
        x = max(0.0, min(100.0, (float(value) - low) / span * 100.0))
        mk.append(
            f'<div class="mk" style="left:{x:.0f}%;background:{color}"></div>'
            f'<div class="lbl" style="left:{x:.0f}%;color:{color}">{_html.escape(label)}</div>'
        )
    return (
        '<div class="sa-rangebar">' + "".join(mk) + "</div>"
        '<div style="display:flex;justify-content:space-between;'
        "font-family:'IBM Plex Mono',monospace;font-size:8px;color:#8a949a\">"
        f"<span>{low:g}</span><span>{high:g}</span></div>"
    )
