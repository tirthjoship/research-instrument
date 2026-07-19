"""Treemap colour lenses + HTML builder for the portfolio book view.

Tiles are display-only (no click) — a raw HTML anchor's ?inspect=TICKER
click used to drive the shared inspect panel, but that pattern caused real
browser navigations on Streamlit Cloud, wiping session state. Use the
"Inspect a holding" selectbox (positions.py) to open a holding's detail.
"""

from __future__ import annotations

from typing import Any

from adapters.visualization.components.squarify import squarify
from adapters.visualization.portfolio_view import PortfolioRow

LENSES: tuple[str, str, str] = ("pnl", "today", "verdict")

# (upper-exclusive bound, bg, fg) — capped at ±25
_PNL_BINS = [
    (25.0, "#15803D", "#FFFFFF"),
    (8.0, "#22C55E", "#0F172A"),
    (0.0, "#BBF7D0", "#0F172A"),
    (-8.0, "#FECACA", "#0F172A"),
    (-25.0, "#F87171", "#FFFFFF"),
]
_PNL_FLOOR = ("#DC2626", "#FFFFFF")

_VERDICT_COLORS = {
    "REDUCE": ("#DC2626", "#FFFFFF"),
    "TRIM": ("#F87171", "#FFFFFF"),
    "REVIEW": ("#FBBF24", "#0F172A"),
    "HOLD": ("#22C55E", "#0F172A"),
    "ADD_OK": ("#15803D", "#FFFFFF"),
}
_VERDICT_DEFAULT = ("#E5E7EB", "#64748B")


def _bin(value: float) -> tuple[str, str]:
    if value >= 25.0:
        return _PNL_BINS[0][1], _PNL_BINS[0][2]
    if value >= 8.0:
        return _PNL_BINS[1][1], _PNL_BINS[1][2]
    if value >= 0.0:
        return _PNL_BINS[2][1], _PNL_BINS[2][2]
    if value > -8.0:
        return _PNL_BINS[3][1], _PNL_BINS[3][2]
    if value > -25.0:
        return _PNL_BINS[4][1], _PNL_BINS[4][2]
    return _PNL_FLOOR


def lens_color(row: dict[str, Any], lens: str) -> tuple[str, str]:
    """Return (background, foreground) hex for a holding under ``lens``."""
    if lens == "pnl":
        return _bin(float(row.get("pnl") or 0.0))
    if lens == "today":
        # amplify intraday so small daily moves are legible, same bins
        return _bin(float(row.get("today") or 0.0) * 5.0)
    return _VERDICT_COLORS.get(str(row.get("verdict") or ""), _VERDICT_DEFAULT)


# ---------------------------------------------------------------------------
# HTML builder — squarified treemap (sector-grouped or flat)
# ---------------------------------------------------------------------------

_SECTOR_LABELS: dict[str, str] = {
    "Tech": "Technology",
    "Fin": "Financials",
    "Cons": "Consumer",
    "Indus": "Industrials",
    "Comm": "Communications",
    "Mat": "Materials",
    "Util": "Utilities",
    "RE": "Real Estate",
}


def _lens_value_str(row: PortfolioRow, lens: str) -> str:
    if lens == "today":
        return f"{'+' if row.today >= 0 else ''}{row.today:.1f}%"
    if lens == "pnl":
        return f"{'+' if row.pnl >= 0 else ''}{row.pnl:.1f}%"
    return row.verdict


def _tile_html(
    row: PortfolioRow, lens: str, x: float, y: float, w: float, h: float
) -> str:
    bg, fg = lens_color(
        {"pnl": row.pnl, "today": row.today, "verdict": row.verdict}, lens
    )
    area = w * h
    show = area > 1100
    big = area > 4200
    label = ""
    if show:
        fs = ".9rem" if big else ".68rem"
        label = (
            f"<div style=\"font-family:'Fraunces',serif;font-weight:700;"
            f"font-size:{fs};line-height:1;white-space:nowrap;overflow:hidden;"
            f'text-overflow:ellipsis;">{row.ticker}</div>'
        )
        if big:
            label += (
                f"<div style=\"font-family:'IBM Plex Mono',monospace;font-size:.62rem;"
                f'font-weight:600;">{_lens_value_str(row, lens)}</div>'
            )
    tip = (
        '<div class="pf-tip">'
        f'<div class="pf-tip-tt">{row.ticker} · {row.verdict or "—"}</div>'
        f'<div class="pf-tip-row"><span>Weight</span><b>{row.weight:.1f}%</b></div>'
        f'<div class="pf-tip-row"><span>Lifetime</span>'
        f'<b>{"+" if row.pnl >= 0 else ""}{row.pnl:.1f}%</b></div>'
        f'<div class="pf-tip-row"><span>Today</span>'
        f'<b>{"+" if row.today >= 0 else ""}{row.today:.1f}%</b></div>'
        "</div>"
    )
    return (
        f'<div class="pf-tile" '
        f'style="left:{x:.1f}px;top:{y:.1f}px;width:{max(w - 2, 0):.1f}px;'
        f'height:{max(h - 2, 0):.1f}px;background:{bg};color:{fg};">{label}{tip}</div>'
    )


def build_treemap_html(
    rows: list[PortfolioRow],
    *,
    lens: str,
    width: float,
    height: float,
    flat: bool = False,
) -> str:
    """Return a self-contained HTML string for the portfolio treemap.

    Args:
        rows: Holdings to render.
        lens: Colour lens — ``"pnl"``, ``"today"``, or ``"verdict"``.
        width: Canvas width in pixels.
        height: Canvas height in pixels.
        flat: If ``True``, skip sector grouping and pack all tiles together.

    Returns:
        HTML string (``<div class="pf-stage">…</div>``) or empty string when
        ``rows`` is empty.
    """
    if not rows:
        return ""
    tiles: list[str] = []
    if flat:
        ordered = sorted(rows, key=lambda r: r.weight, reverse=True)
        rects = squarify([r.weight for r in ordered], 0.0, 0.0, width, height)
        for rect in rects:
            r = ordered[rect.index]
            tiles.append(_tile_html(r, lens, rect.x, rect.y, rect.w, rect.h))
    else:
        by_sec: dict[str, list[PortfolioRow]] = {}
        for r in rows:
            by_sec.setdefault(r.sector, []).append(r)
        secs = sorted(
            by_sec.items(),
            key=lambda kv: sum(x.weight for x in kv[1]),
            reverse=True,
        )
        sec_weights = [sum(x.weight for x in items) for _, items in secs]
        sec_rects = squarify(sec_weights, 0.0, 0.0, width, height)
        for rect in sec_rects:
            name, items = secs[rect.index]
            sw = sum(x.weight for x in items)
            label = _SECTOR_LABELS.get(name, name)
            tiles.append(
                f'<div class="pf-sec" style="left:{rect.x:.1f}px;top:{rect.y:.1f}px;'
                f'width:{rect.w - 3:.1f}px;height:{rect.h - 3:.1f}px;">'
                f'<div class="pf-sechdr"><span>{label}</span>'
                f"<span>{sw:.0f}%</span></div></div>"
            )
            items_sorted = sorted(items, key=lambda r: r.weight, reverse=True)
            inner = squarify(
                [r.weight for r in items_sorted],
                rect.x,
                rect.y + 16,
                rect.w - 3,
                rect.h - 3 - 16,
            )
            for ir in inner:
                tiles.append(
                    _tile_html(items_sorted[ir.index], lens, ir.x, ir.y, ir.w, ir.h)
                )
    return (
        f'<div class="pf-stage" style="height:{height:.0f}px;">{"".join(tiles)}</div>'
    )
