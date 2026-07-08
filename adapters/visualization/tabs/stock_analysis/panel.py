"""Shared deep-dive panel skeleton (spec D9): eyebrow+chips -> claim -> strip -> 2 viz -> verdicts -> drill."""

from __future__ import annotations

import html as _html
from dataclasses import dataclass

_VB_ICON = {"pos": "✓", "cau": "⚠", "neu": "◦", "stop": "⛔"}


@dataclass(frozen=True)
class Verdict:
    tone: str  # pos | cau | neu | stop
    text: str


def _verdict_html(v: Verdict) -> str:
    cls = v.tone if v.tone in _VB_ICON else "neu"
    return (
        f'<div class="sa-vb {cls}"><span class="i">{_VB_ICON.get(cls, "◦")}</span>'
        f"<span>{_html.escape(v.text)}</span></div>"
    )


def build_panel(
    *,
    number: int,
    name: str,
    dot_colour: str,
    info_html: str,
    chips_html: str,
    claim: str,
    reframe: str,
    strip_html: str,
    viz_left: str,
    viz_right: str,
    verdicts: list[Verdict],
    drill: str,
    reframe_html: str | None = None,
    viz_two_modifier: str = "",
) -> str:
    e = _html.escape
    verds = "".join(_verdict_html(v) for v in verdicts)
    two_mod = f" sa-pnl-two{viz_two_modifier}" if viz_two_modifier else " sa-pnl-two"
    col_cls = "sa-buzz-col" if viz_two_modifier == "--buzz" else ""

    def col_open() -> str:
        return f'<div class="{col_cls}">' if col_cls else "<div>"

    if viz_left and viz_right:
        two = (
            f'<div class="{two_mod.strip()}">{col_open()}{viz_left}</div>'
            f"{col_open()}{viz_right}</div></div>"
        )
    elif viz_left:
        two = f'<div class="sa-pnl-viz-full">{viz_left}</div>'
    else:
        two = ""
    reline = reframe_html if reframe_html is not None else e(reframe)
    # NOTE: `drill` is intentionally not rendered — the deeper "open full …" view
    # it described was never built (its data is DATA-GAP), so a non-functional
    # link is misleading. Param kept for call-site compatibility.
    _ = drill
    return (
        '<div class="sa-pnl"><div class="sa-pnl-head">'
        f'<span class="sa-pnl-eyebrow"><span class="sa-pnl-dot" style="color:{e(dot_colour)}">●</span> '
        f"{number} · {e(name)} {info_html}</span>"
        f'<span class="sa-pnl-chips">{chips_html}</span></div>'
        f'<div class="sa-pnl-claim">{e(claim)}</div>'
        f'<div class="sa-pnl-reline">{reline}</div>'
        f"{strip_html}{two}"
        f'<div class="sa-verdrow">{verds}</div></div>'
    )
