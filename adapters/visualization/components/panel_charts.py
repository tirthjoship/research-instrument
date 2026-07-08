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


def rating_distribution_bars(
    rows: Sequence[tuple[str, float, str]], *, label_width: int = 74, width: int = 150
) -> str:
    """Analyst rating counts — slop-safe tier labels, mockup purple/grey bars."""
    vals = [abs(v) for _, v, _ in rows] or [1.0]
    hi = max(vals) or 1.0
    out = []
    for label, value, bar_bg in rows:
        w = int(round(abs(value) / hi * width))
        out.append(
            '<div style="display:flex;align-items:center;gap:8px;margin:4px 0;'
            "font-family:'IBM Plex Mono',monospace;font-size:9px\">"
            f'<span style="width:{label_width}px;color:var(--ri-ink2)">'
            f"{_html.escape(label)}</span>"
            f'<div style="height:11px;border-radius:3px;width:{w}px;background:{bar_bg}"></div>'
            f'<span style="color:var(--ri-ink2)">{round(value)}</span></div>'
        )
    return "".join(out)


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


def stacked_bar(segments: Sequence[tuple[str, float, str]], *, height: int = 16) -> str:
    """One segmented horizontal bar (e.g. holder composition) + a wrapping legend.

    ``segments`` is ``(label, value, colour)``; widths are value/total. A single
    bar avoids the multi-row label wrapping of separate bars and reads as one
    whole split into parts.
    """
    total = sum(max(0.0, v) for _, v, _ in segments) or 1.0
    seg = "".join(
        f'<div style="width:{max(0.0, v) / total * 100:.1f}%;background:{col}"></div>'
        for _, v, col in segments
    )
    bar = (
        f'<div style="display:flex;height:{height}px;border-radius:6px;'
        f'overflow:hidden;background:#eef1f2">{seg}</div>'
    )
    legend = "".join(
        '<span style="display:inline-flex;align-items:center;gap:5px;margin:0 12px 0 0;'
        "font-family:'IBM Plex Mono',monospace;font-size:9.5px;color:var(--ri-ink2)\">"
        f'<i style="width:9px;height:9px;border-radius:2px;background:{col};'
        'display:inline-block"></i>'
        f"{_html.escape(label)} <b>{round(v)}%</b></span>"
        for label, v, col in segments
    )
    return bar + f'<div style="margin-top:7px">{legend}</div>'


def horizon_compare_bars(
    rows: Sequence[tuple[str, float, float, bool]], *, unit: str = "%", width: int = 150
) -> str:
    """Per-horizon stock-vs-benchmark bars: a bold stock bar over a muted S&P bar.

    Each row is ``(label, stock_value, benchmark_value, is_focus)``. Bars share one
    scale (max abs across both series). The focus row's stock bar is amber; others
    petrol. Generalises the single "vs S&P" tile to every horizon — descriptive,
    never a call.
    """
    vals = [abs(v) for _, s, p, _ in rows for v in (s, p)] or [1.0]
    hi = max(vals) or 1.0
    out = []
    for label, sv, pv, focus in rows:
        sw = int(round(abs(sv) / hi * width))
        pw = int(round(abs(pv) / hi * width))
        scol = "var(--ri-amber)" if focus else "#0F6E80"
        weight = "700" if focus else "400"
        out.append(
            "<div style=\"margin:5px 0;font-family:'IBM Plex Mono',monospace;"
            'font-size:9px">'
            '<div style="display:flex;align-items:center;gap:8px">'
            f'<span style="width:26px;color:var(--ri-ink2);font-weight:{weight}">'
            f"{_html.escape(label)}</span>"
            '<div style="flex:1">'
            '<div style="display:flex;align-items:center;gap:6px;margin-bottom:2px">'
            f'<div style="height:8px;border-radius:3px;width:{sw}px;background:{scol}"></div>'
            f'<span style="font-weight:700">{sv:+.0f}{_html.escape(unit)}</span></div>'
            '<div style="display:flex;align-items:center;gap:6px">'
            f'<div style="height:6px;border-radius:3px;width:{pw}px;background:#cdd7d9"></div>'
            f'<span style="color:var(--ri-muted)">S&P {pv:+.0f}{_html.escape(unit)}</span>'
            "</div></div></div></div>"
        )
    return "".join(out)


def trend_lines(
    series: type_series,
    *,
    height: int = 70,
    width: int = 300,
    unit: str = "",
    x_labels: tuple[str, str] | None = None,
    label_lines: bool = True,
) -> str:
    """One or more polylines on a shared y-scale, with HTML axis numbers.

    Mirrors ``bars_and_line``: the crisp y-axis (max/min) and optional x-axis
    (first/last period) labels are rendered as HTML around the SVG so they are
    not distorted by ``preserveAspectRatio="none"``. '' if no series have data.

    ``label_lines=False`` suppresses the inline end-of-line text labels even
    with 2+ series — for callers whose lines can converge at the same value
    (the labels would otherwise overlap into unreadable text) and who already
    name each series in a caption instead.
    """
    series = [(lbl, vals, col) for lbl, vals, col in series if vals]
    if not series:
        return ""
    allv = [v for _, vals, _ in series for v in vals]
    lo, hi = min(allv), max(allv)
    span = (hi - lo) or 1.0
    multi = len(series) > 1 and label_lines
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
        # inline series label only when there are 2+ lines to tell apart;
        # a single line is already named by the panel subhead.
        if multi:
            lines.append(
                f'<text x="{width - 2}" y="{height - 6 - ((vals[-1] - lo) / span) * (height - 14):.1f}" '
                f'font-size="7" fill="{col}" text-anchor="end">{_html.escape(lbl)}</text>'
            )
    svg = (
        f'<svg width="100%" height="{height}" viewBox="0 0 {width} {height}" '
        'preserveAspectRatio="none" '
        "style=\"font-family:'IBM Plex Mono',monospace;overflow:visible\">"
        + "".join(lines)
        + "</svg>"
    )
    yaxis = (
        '<div style="display:flex;flex-direction:column;justify-content:space-between;'
        'text-align:right;min-width:26px;padding:2px 2px 0 0">'
        + _axis_label(f"{fmt_num(hi)}{unit}")
        + _axis_label(f"{fmt_num(lo)}{unit}")
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


def volume_bars(
    rows: Sequence[tuple[str, float] | tuple[str, float, str]],
    *,
    width: int = 300,
    height: int | None = None,
    highlight_idx: int | None = None,
    show_zero_stubs: bool = True,
    css_class: str = "",
    compact: bool = False,
) -> str:
    """Vertical mention-volume bars with readable axes. Empty -> empty string."""
    if not rows:
        return ""
    parsed: list[tuple[str, float, str]] = []
    for row in rows:
        if len(row) >= 3:
            parsed.append((str(row[0]), float(row[1]), str(row[2])))
        else:
            parsed.append((str(row[0]), float(row[1]), str(row[0])))
    vals = [max(0.0, v) for _, v, _ in parsed]
    hi = max(vals) or 1.0
    nonzero = sum(1 for v in vals if v > 0)
    if height is None:
        height = 56 if compact or nonzero <= 4 else 72
    n = len(parsed)
    y_axis_w = 24
    plot_w = width - y_axis_w - 2
    gap = 6 if n <= 14 else max(2, 6 - n // 10)
    bar_w = max(8 if n <= 14 else 3, min(14, (plot_w - gap * (n + 1)) // max(n, 1)))
    top = 12
    baseline_y = height - 14
    plot_h = baseline_y - top
    if highlight_idx is None and vals:
        highlight_idx = max(range(n), key=lambda i: vals[i])
    rects: list[str] = []
    label_idxs: set[int] = {0, n - 1}
    if highlight_idx is not None:
        label_idxs.add(highlight_idx)
    for i, (label, value, iso_date) in enumerate(parsed):
        if value > 0:
            h = max(4, int(round(value / hi * plot_h)))
            fill = "#7c5cbf" if i == highlight_idx else "#b9a0d6"
        elif show_zero_stubs:
            h = 3
            fill = "#dde2e4"
        else:
            continue
        x = y_axis_w + gap + i * (bar_w + gap)
        y = baseline_y - h
        cnt = int(value)
        word = "mentions" if cnt != 1 else "mention"
        tip = _html.escape(f"{iso_date}: {cnt} {word}")
        tip_short = _html.escape(f"{label} · {cnt}")
        cx = x + bar_w / 2
        rects.append(
            f'<g class="sa-buzz-bar">'
            f"<title>{tip}</title>"
            f'<rect x="{x}" y="{y}" width="{bar_w}" height="{h}" fill="{fill}"/>'
            f'<text class="sa-buzz-bar-tip" x="{cx:.1f}" y="{max(top + 2, y - 3):.1f}" '
            f'text-anchor="middle">{tip_short}</text>'
            f"</g>"
        )
    axis_labels: list[str] = []
    hi_lbl = str(int(hi)) if hi == int(hi) else f"{hi:.1f}"
    axis_labels.append(
        f'<text x="{y_axis_w - 3}" y="{baseline_y + 3}" text-anchor="end" '
        f'font-size="7.5" fill="#8a949a">0</text>'
    )
    axis_labels.append(
        f'<text x="{y_axis_w - 3}" y="{top + 4}" text-anchor="end" '
        f'font-size="7.5" fill="#8a949a">{_html.escape(hi_lbl)}</text>'
    )
    for idx in sorted(label_idxs):
        cx = y_axis_w + gap + idx * (bar_w + gap) + bar_w / 2
        axis_labels.append(
            f'<text x="{cx:.1f}" y="{height - 2}" text-anchor="middle" '
            f'font-size="7" fill="#8a949a">{_html.escape(parsed[idx][0])}</text>'
        )
    cls = f' class="{css_class}"' if css_class else ""
    return (
        f'<svg width="100%" height="{height}" viewBox="0 0 {width} {height}" '
        f'xmlns="http://www.w3.org/2000/svg" preserveAspectRatio="xMidYMid meet"{cls}>'
        f'<line x1="{y_axis_w}" y1="{baseline_y}" x2="{width}" y2="{baseline_y}" '
        f'stroke="#eef1f1"/>'
        f'<line x1="{y_axis_w}" y1="{top}" x2="{y_axis_w}" y2="{baseline_y}" '
        f'stroke="#eef1f1"/>'
        f'<g>{"".join(rects)}</g>'
        f'<g>{"".join(axis_labels)}</g></svg>'
    )


type_bubble_rows = Sequence[tuple[str, float, float, bool]]


def group_bubbles(
    rows: type_bubble_rows, *, width: int = 300, height: int = 132
) -> str:
    """Supply-chain group map: x = market-cap rank (larger → right), y = 1-week
    move, bubble radius ~ relative market cap. Subject ticker in petrol, peers
    grey. ``rows`` is ``(ticker, market_cap, one_week_pct, is_subject)``; entries
    with a non-positive market cap are dropped. '' if fewer than 2 remain.
    """
    usable = [r for r in rows if r[1] > 0]
    if len(usable) < 2:
        return ""
    ordered = sorted(usable, key=lambda r: r[1])
    caps = [r[1] for r in ordered]
    lo_cap, hi_cap = min(caps), max(caps)
    cap_span = (hi_cap - lo_cap) or 1.0
    moves = [r[2] for r in ordered] + [0.0]
    lo_m, hi_m = min(moves), max(moves)
    m_span = (hi_m - lo_m) or 1.0
    n = len(ordered)
    slot = width / n
    r_min, r_max = 9.0, 24.0
    plot_h = height - 44

    def y(move: float) -> float:
        return height - 6 - ((move - lo_m) / m_span) * plot_h

    circles = []
    for i, (ticker, cap, move, is_subject) in enumerate(ordered):
        cx = slot * i + slot / 2
        cy = y(move) - 10
        frac = (cap - lo_cap) / cap_span
        radius = r_min + frac * (r_max - r_min)
        fill = "rgba(15,110,128,.5)" if is_subject else "rgba(91,113,120,.32)"
        stroke = "#0F6E80" if is_subject else "#7d8a90"
        weight = "700" if is_subject else "400"
        fs = 9 if is_subject else 7.5
        text_col = "#fff" if is_subject else "#33403f"
        circles.append(
            f'<circle cx="{cx:.1f}" cy="{cy:.1f}" r="{radius:.1f}" fill="{fill}" '
            f'stroke="{stroke}"/>'
            f'<text x="{cx:.1f}" y="{cy + 3:.1f}" font-size="{fs}" fill="{text_col}" '
            f'text-anchor="middle" font-weight="{weight}">{_html.escape(ticker)}</text>'
        )

    zero_y = y(0.0)
    baseline = (
        f'<line x1="0" y1="{zero_y:.1f}" x2="{width}" y2="{zero_y:.1f}" '
        'stroke="#e6e6e6" stroke-dasharray="3,3"/>'
        f'<text x="2" y="{zero_y - 4:.1f}" font-size="7" fill="#9aa6aa">0%</text>'
    )
    caption = (
        f'<text x="{width / 2:.1f}" y="{height - 2}" font-size="7" fill="#9aa6aa" '
        'text-anchor="middle">larger market cap →</text>'
    )
    return (
        f'<svg width="100%" height="{height}" viewBox="0 0 {width} {height}" '
        'preserveAspectRatio="none">' + baseline + "".join(circles) + caption + "</svg>"
    )


def _normalize_series(vals: list[float]) -> list[float]:
    lo, hi = min(vals), max(vals)
    span = (hi - lo) or 1.0
    return [(v - lo) / span for v in vals]


def sentiment_source_row(label: str, mean: float, *, track_width: int = 120) -> str:
    """Diverging bar for a News/Social bucket mean in [-1, 1]."""
    clamped = max(-1.0, min(1.0, mean))
    mid = track_width // 2
    if clamped >= 0:
        w = int(abs(clamped) * mid)
        fill = "#2d6a4f"
        style = f"left:{mid}px;width:{w}px;background:{fill}"
    else:
        w = int(abs(clamped) * mid)
        fill = "#b91c1c"
        style = f"left:{mid - w}px;width:{w}px;background:{fill}"
    mean_lbl = f"{mean:+.2f}"
    return (
        '<div class="sa-srcrow">'
        f'<span class="lab">{_html.escape(label)}</span>'
        f'<div class="sa-srctrack" style="max-width:{track_width}px">'
        f'<span class="sa-srcmid"></span>'
        f'<span class="sa-srcfill" style="{style}"></span></div>'
        f'<span class="sa-srcval">{mean_lbl}</span></div>'
    )


def sentiment_vs_price_chart(
    sentiment: list[float],
    price: list[float],
    *,
    height: int = 84,
    width: int = 300,
    x_labels: tuple[str, str] | None = None,
) -> str:
    """Dual-line overlay: solid tone (purple) + dashed normalized price (grey).

    Both series are min-max normalized to a shared 0–1 scale for shape comparison
    only — not a return forecast. '' if fewer than 2 aligned points.
    """
    n = min(len(sentiment), len(price))
    if n < 2:
        return ""
    s_vals = _normalize_series([float(v) for v in sentiment[:n]])
    p_vals = _normalize_series([float(v) for v in price[-n:]])
    lo = 0.0
    span = 1.0
    step = width / max(n - 1, 1)

    def y(v: float) -> float:
        return height - 6 - ((v - lo) / span) * (height - 14)

    s_pts = " ".join(f"{i * step:.1f},{y(v):.1f}" for i, v in enumerate(s_vals))
    p_pts = " ".join(f"{i * step:.1f},{y(v):.1f}" for i, v in enumerate(p_vals))
    svg = (
        f'<svg width="100%" height="{height}" viewBox="0 0 {width} {height}" '
        'preserveAspectRatio="none" style="overflow:visible">'
        f'<polyline points="{s_pts}" fill="none" stroke="#5c6bc0" stroke-width="2"/>'
        f'<polyline points="{p_pts}" fill="none" stroke="#9aa6aa" stroke-width="1.8" '
        'stroke-dasharray="4 3"/>'
        "</svg>"
    )
    yaxis = (
        '<div style="display:flex;flex-direction:column;justify-content:space-between;'
        'text-align:right;min-width:26px;padding:2px 2px 0 0">'
        + _axis_label("1")
        + _axis_label("0")
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
