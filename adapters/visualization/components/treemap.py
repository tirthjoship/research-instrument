"""Treemap colour lenses + HTML builder for the portfolio book view."""

from __future__ import annotations

from typing import Any

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
