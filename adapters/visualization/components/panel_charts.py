"""Pure HTML/SVG builders for deep-dive panel comparison + trend visuals."""

from __future__ import annotations

import html as _html
from typing import Sequence

type_peer_rows = Sequence[tuple[str, float, bool]]
type_series = Sequence[tuple[str, list[float], str]]
type_markers = Sequence[tuple[float, str, str]]


def peer_bars(rows: type_peer_rows, *, unit: str = "x", width: int = 150) -> str:
    vals = [abs(v) for _, v, _ in rows] or [1.0]
    hi = max(vals) or 1.0
    out = []
    for label, value, is_self in rows:
        w = int(round(abs(value) / hi * width))
        bar_bg = "var(--ri-amber)" if is_self else "#cdd7d9"
        weight = "700" if is_self else "400"
        out.append(
            '<div style="display:flex;align-items:center;gap:8px;margin:3px 0;'
            "font-family:'IBM Plex Mono',monospace;font-size:9.5px\">"
            f'<span style="width:42px;color:var(--ri-ink2);font-weight:{weight}">{_html.escape(label)}</span>'
            f'<div style="height:10px;border-radius:3px;width:{w}px;background:{bar_bg}"></div>'
            f"<span>{value:g}{_html.escape(unit)}</span></div>"
        )
    return "".join(out)


def trend_lines(series: type_series, *, height: int = 70, width: int = 300) -> str:
    series = [(lbl, vals, col) for lbl, vals, col in series if vals]
    if not series:
        return ""
    allv = [v for _, vals, _ in series for v in vals]
    lo, hi = min(allv), max(allv)
    span = (hi - lo) or 1.0
    lines = []
    for lbl, vals, col in series:
        n = len(vals)
        step = width / max(n - 1, 1)
        pts = " ".join(
            f"{i * step:.1f},{height - 6 - ((v - lo) / span) * (height - 14):.1f}"
            for i, v in enumerate(vals)
        )
        lines.append(
            f'<polyline points="{pts}" fill="none" stroke="{col}" stroke-width="2"/>'
        )
        lines.append(
            f'<text x="{width - 2}" y="{height - 6 - ((vals[-1] - lo) / span) * (height - 14):.1f}" '
            f'font-size="7" fill="{col}" text-anchor="end">{_html.escape(lbl)}</text>'
        )
    return (
        f'<svg width="100%" height="{height}" viewBox="0 0 {width} {height}" '
        f'preserveAspectRatio="none" style="font-family:\'IBM Plex Mono\',monospace">'
        + "".join(lines)
        + "</svg>"
    )


def marker_range(
    low: float,
    high: float,
    markers: type_markers,
    *,
    band: tuple[float, float] | None = None,
) -> str:
    if high <= low:
        return '<div class="sa-pnl-cap">data gap — no range available</div>'
    span = high - low
    band_html = ""
    if band:
        b0 = max(0.0, min(100.0, (band[0] - low) / span * 100))
        b1 = max(0.0, min(100.0, (band[1] - low) / span * 100))
        band_html = (
            f'<div class="band" style="left:{b0:.0f}%;width:{max(0.0, b1 - b0):.0f}%;'
            'background:rgba(15,110,128,.16)"></div>'
        )
    mk = []
    for value, label, colour in markers:
        x = max(0.0, min(100.0, (value - low) / span * 100))
        mk.append(
            f'<div class="mk" style="left:{x:.0f}%;background:{colour}"></div>'
            f'<div class="lbl" style="left:{x:.0f}%;color:{colour}">{_html.escape(label)}</div>'
        )
    return (
        '<div class="sa-rangebar">' + band_html + "".join(mk) + "</div>"
        '<div style="display:flex;justify-content:space-between;'
        "font-family:'IBM Plex Mono',monospace;font-size:8px;color:var(--ri-muted)\">"
        f"<span>{low:g}</span><span>{high:g}</span></div>"
    )
