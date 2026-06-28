"""Pure HTML/SVG builders for deep-dive panel comparison + trend visuals."""

from __future__ import annotations

import html as _html
from typing import Sequence

type_peer_rows = Sequence[tuple[str, float, bool]]
type_series = Sequence[tuple[str, list[float], str]]
type_markers = Sequence[tuple[float, str, str]]


def fmt_num(v: float) -> str:
    """Display a metric value without raw-float noise.

    1 decimal for |v|>=10, 2 for smaller ratios, trailing zeros stripped:
    29.4839 -> '29.5', 52.0 -> '52', 0.59 -> '0.59', 172.139 -> '172.1'.
    """
    s = f"{v:.1f}" if abs(v) >= 10 else f"{v:.2f}"
    return s.rstrip("0").rstrip(".") or "0"


def peer_bars(rows: type_peer_rows, *, unit: str = "x", width: int = 150) -> str:
    vals = [abs(v) for _, v, _ in rows] or [1.0]
    hi = max(vals) or 1.0
    out = []
    for label, value, is_self in rows:
        w = int(round(abs(value) / hi * width))
        bar_bg = "var(--ri-amber)" if is_self else "#cdd7d9"
        weight = "700" if is_self else "400"
        # whole numbers for percentage shares; 1-decimal for multiples/ratios
        disp = f"{round(value)}" if unit == "%" else fmt_num(value)
        out.append(
            '<div style="display:flex;align-items:center;gap:8px;margin:3px 0;'
            "font-family:'IBM Plex Mono',monospace;font-size:9.5px\">"
            f'<span style="width:42px;color:var(--ri-ink2);font-weight:{weight}">{_html.escape(label)}</span>'
            f'<div style="height:10px;border-radius:3px;width:{w}px;background:{bar_bg}"></div>'
            f"<span>{disp}{_html.escape(unit)}</span></div>"
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


def _axis_label(text: str) -> str:
    return (
        "<span style=\"font-family:'IBM Plex Mono',monospace;font-size:7.5px;"
        f'color:var(--ri-muted)">{_html.escape(text)}</span>'
    )


def bars_and_line(
    bars: list[float],
    line: list[float],
    *,
    height: int = 84,
    width: int = 300,
    bar_color: str = "#bfe0c8",
    line_color: str = "#1971c2",
    unit: str = "",
    x_labels: tuple[str, str] | None = None,
) -> str:
    """Revenue bars + net-income line on a shared axis, with HTML axis numbers.

    Filled bars give scale, the line tracks earnings, a zero baseline anchors them.
    Crisp y-axis (max/min) and x-axis (first/last) labels are rendered as HTML around
    the SVG so they aren't distorted by preserveAspectRatio="none". '' if < 2 bars.
    """
    bars = [float(v) for v in bars if v == v]
    line = [float(v) for v in line if v == v]
    if len(bars) < 2:
        return ""
    n = len(bars)
    slot = width / n
    bw = slot * 0.6
    allv = bars + line
    lo = min(0.0, min(allv))
    hi = max(allv) or 1.0
    span = (hi - lo) or 1.0
    base = height - 6

    def y(v: float) -> float:
        return 6.0 + (hi - v) / span * (base - 6.0)

    y0 = y(0.0)
    rects = "".join(
        f'<rect x="{i * slot + (slot - bw) / 2:.1f}" y="{y(v):.1f}" '
        f'width="{bw:.1f}" height="{max(0.0, y0 - y(v)):.1f}" fill="{bar_color}" rx="1.5"/>'
        for i, v in enumerate(bars)
    )
    centers = [i * slot + slot / 2 for i in range(n)]
    line_svg = ""
    if len(line) >= 2:
        m = min(len(line), n)
        pts = " ".join(f"{centers[i]:.1f},{y(line[i]):.1f}" for i in range(m))
        dots = "".join(
            f'<circle cx="{centers[i]:.1f}" cy="{y(line[i]):.1f}" r="1.6" fill="{line_color}"/>'
            for i in range(m)
        )
        line_svg = (
            f'<polyline points="{pts}" fill="none" stroke="{line_color}" stroke-width="1.8"/>'
            + dots
        )
    baseline = (
        f'<line x1="0" y1="{base:.1f}" x2="{width}" y2="{base:.1f}" stroke="#e2e2e2"/>'
    )
    svg = (
        f'<svg width="100%" height="{height}" viewBox="0 0 {width} {height}" '
        'preserveAspectRatio="none" style="overflow:visible">'
        + baseline
        + rects
        + line_svg
        + "</svg>"
    )
    ymax = f"{fmt_num(hi)}{unit}"
    ymin = f"{fmt_num(lo)}{unit}"
    yaxis = (
        '<div style="display:flex;flex-direction:column;justify-content:space-between;'
        'text-align:right;min-width:26px;padding:2px 2px 0 0">'
        + _axis_label(ymax)
        + _axis_label(ymin)
        + "</div>"
    )
    xaxis = ""
    if x_labels:
        xaxis = (
            '<div style="display:flex;justify-content:space-between;margin:1px 0 0 28px">'
            + _axis_label(x_labels[0])
            + _axis_label(x_labels[1])
            + "</div>"
        )
    return (
        '<div style="display:flex;gap:3px;align-items:stretch">'
        + yaxis
        + f'<div style="flex:1">{svg}</div></div>'
        + xaxis
    )


def marker_range(
    low: float,
    high: float,
    markers: type_markers,
    *,
    band: tuple[float, float] | None = None,
    left_label: str | None = None,
    right_label: str | None = None,
    gradient: bool = False,
) -> str:
    """Horizontal range bar with point markers.

    ``left_label``/``right_label`` override the plain numeric end labels (e.g.
    "bear $150" / "bull $260"). ``gradient=True`` paints a bear→bull (warm→green)
    track and colours the end labels accordingly — descriptive of the low/high
    case, not a trade call.
    """
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
    bar_cls = "sa-rangebar bearbull" if gradient else "sa-rangebar"
    ll = _html.escape(left_label) if left_label is not None else fmt_num(low)
    rl = _html.escape(right_label) if right_label is not None else fmt_num(high)
    # bear end warm/amber, bull end green — only when the gradient semantics apply
    lcol = "#7a4a08" if gradient else "var(--ri-muted)"
    rcol = "#1f5130" if gradient else "var(--ri-muted)"
    return (
        f'<div class="{bar_cls}">' + band_html + "".join(mk) + "</div>"
        '<div style="display:flex;justify-content:space-between;'
        "font-family:'IBM Plex Mono',monospace;font-size:8px\">"
        f'<span style="color:{lcol};font-weight:700">{ll}</span>'
        f'<span style="color:{rcol};font-weight:700">{rl}</span></div>'
    )
