"""Fit-vs-book card + snowflake-fit two-column section + colour key (spec D5/D-GLOBAL-C)."""

from __future__ import annotations

import html as _html
from dataclasses import dataclass
from typing import Any

from adapters.visualization.components.radar_svg import RadarAxis, build_radar_svg

_SEVERITY_CLASS = {"WARNING": "stop", "CAUTION": "cau", "INFO": "neu"}

_FALSIFIED = (
    "Return-forecast hypothesis: tested across the universe, FALSIFIED (zero IC). "
    "Evidence and fit only, never a return call."
)

COLOUR_KEY_HTML = (
    '<div class="sa-ckey"><b>Colour</b> = where a measure sits vs peers or a fixed threshold — '
    "descriptive, never good/bad or a forecast."
    '<span class="sw" style="background:var(--ri-amber)"></span>atypical (top/bottom quartile)'
    '<span class="sw" style="background:var(--ri-green)"></span>passes a stated threshold'
    '<span class="sw" style="background:var(--ri-muted)"></span>typical. Hover any ⓘ for the exact rule.</div>'
)


@dataclass(frozen=True)
class FitCardView:
    grade: str
    summary: str
    flags: tuple[tuple[str, str], ...]
    falsified_note: str


def build_fit_card_view(fit: Any) -> FitCardView:
    if fit is None:
        return FitCardView(
            grade="—",
            summary="No fit assessment available.",
            flags=(),
            falsified_note=_FALSIFIED,
        )
    flags = tuple(
        (
            _SEVERITY_CLASS.get(str(getattr(f, "severity", "INFO")).upper(), "neu"),
            str(getattr(f, "message", "")),
        )
        for f in (getattr(fit, "fit_flags", ()) or ())
    )
    return FitCardView(
        grade=str(getattr(fit, "evidence_grade", "") or "—"),
        summary=str(getattr(fit, "summary", "") or ""),
        flags=flags,
        falsified_note=_FALSIFIED,
    )


# severity -> (icon, icon colour token). Inline-styled (these classes are NOT in styles.py).
_CLASS_ICON = {"stop": "⛔", "cau": "⚠", "neu": "◦"}
_ICON_COLOUR = {
    "stop": "var(--ri-crimson)",
    "cau": "var(--ri-amber)",
    "neu": "var(--ri-muted)",
}


def build_fit_card_html(view: FitCardView) -> str:
    e = _html.escape
    flags = "".join(
        '<div style="display:flex;gap:7px;margin:5px 0;font-size:11px;color:var(--ri-ink2);line-height:1.4">'
        f"<span style=\"font-family:'IBM Plex Mono',monospace;font-weight:700;flex:0 0 auto;"
        f'color:{_ICON_COLOUR.get(cls, "var(--ri-muted)")}">{_CLASS_ICON.get(cls, "◦")}</span>'
        f"<span>{e(msg)}</span></div>"
        for cls, msg in view.flags
    )
    return (
        '<div><div style="display:flex;gap:9px;align-items:center">'
        f'<span class="sa-grade"><span class="dot"></span>GRADE {e(view.grade)}</span>'
        '<span class="sa-eyebrow">fit vs your book</span></div>'
        f'<div style="color:var(--ri-ink);font-size:12.5px;margin:8px 0">{e(view.summary)}</div>'
        f"{flags}"
        '<div style="margin-top:9px;font-size:10.5px;line-height:1.4;color:#7a1414;'
        'background:rgba(206,47,38,.06);border:1px solid rgba(206,47,38,.28);border-radius:7px;padding:7px 9px">'
        f"{e(view.falsified_note)} → Trust</div></div>"
    )


def build_snowflake_fit_html(axes: list[RadarAxis], fit_view: FitCardView) -> str:
    radar = build_radar_svg(axes)
    legend = (
        '<div class="sa-lgnd"><span><i style="background:#0F6E80"></i>this stock</span>'
        '<span><i style="background:#9aa6aa"></i>median (50th)</span></div>'
    )
    left = (
        f'<div><div style="max-width:230px;margin:0 auto">{radar}</div>{legend}</div>'
    )
    right = build_fit_card_html(fit_view)
    return (
        '<div class="sa-eyebrow">Evidence shape + fit</div>'
        "<div style=\"font-family:'Fraunces',serif;font-size:16px;font-weight:700;margin:2px 0 6px\">"
        "How it looks, and how it fits your book</div>"
        f'<div class="sa-twocol-fit">{left}{right}</div>'
    )
