"""Risk tab — v8 status-first layout (Task 12 / ADR-052).

Architecture
------------
_compose(macro)  →  pure string composer (no Streamlit, fully testable)
render()         →  Streamlit entrypoint; calls load_brief_summary() then
                    st.markdown(_compose(macro)) + render_risk_second_opinion()

Section order (matches approved mockup risk-v8.html):
  _header → _status_banner → _contract_legend → _vitals → _lens_nav →
  _standing → _dials → _grill_drill → _evidence_bands → _factor_chart →
  _enb_section → _sector_section → _who_owns → _drift →
  render_risk_second_opinion → _teach → _flags_footer
"""

from __future__ import annotations

import html as _html
from typing import Any

import streamlit as st

from adapters.visualization.components.risk_second_opinion import (
    render_risk_second_opinion,
)
from adapters.visualization.components.tooltip import tooltip
from adapters.visualization.data_loader import load_brief_summary
from domain.risk_rubric import classify_net_beta

# ── colour constants (mirror risk-v8.html :root) ───────────────────────────
_OK = "#15803d"
_OK_L = "#e7f4ec"
_AMBER = "#b45309"
_AMBER_L = "#fbf0dc"
_AMBER_B = "#ecdcb6"
_G0 = "#E2E8F0"
_G1 = "#94A3B8"
_G2 = "#475569"
_INK = "#0f1c1f"
_MUT = "#5b7178"
_FAINT = "#94a8ad"
_LINE = "#dde7e9"
_CARD = "#ffffff"
_PETROL = "#0F6E80"
_PETROL_L = "#e6f1f3"
_PETROL_D = "#0a5260"

_FLAG_MEANING = {
    "SYSTEMATIC_DOMINANT": (
        "Most of the book's movement is one market-wide bet, not stock picking.",
        "Adding 'one more name' will not diversify this — only a different asset class or hedge changes it.",
    ),
    "FACTOR_DOMINANCE": (
        "One macro factor (e.g. the market or rates) explains an outsized share of risk.",
        "Check whether you MEANT to make that macro bet; trim names that all load on it if not.",
    ),
    "DRIFT": (
        "The book's factor mix moved materially since the last review.",
        "Re-read the latest weekly brief and confirm the new tilt is intentional.",
    ),
}

# ── Shared scale parameters for the beta strip (0..100 %) ──────────────────
_BETA_DOMAIN_LO = -0.5
_BETA_DOMAIN_HI = 2.0
_BETA_DOMAIN_RANGE = _BETA_DOMAIN_HI - _BETA_DOMAIN_LO
_SHARE_FLAG_PCT = 60.0  # 60% flag line on the systematic-share strip


# ---------------------------------------------------------------------------
# Helper: clamp + map a value to 0..100% on a [lo, hi] strip
# ---------------------------------------------------------------------------


def _strip_pct(value: float, lo: float, hi: float) -> float:
    return max(0.0, min(100.0, (value - lo) / (hi - lo) * 100.0))


# ===========================================================================
# Section composers — each returns an HTML string
# ===========================================================================


def _header() -> str:
    return (
        '<div class="eyebrow" style="font-family:\'IBM Plex Mono\',monospace;'
        "font-size:11px;letter-spacing:.2em;text-transform:uppercase;"
        f'color:{_PETROL};margin-bottom:8px">Portfolio Risk · full methodology</div>'
        '<h1 class="ri-h1">Where your book <em>stands</em></h1>'
        '<p class="lede" style="font-size:14px;color:var(--risk-mut,#5b7178);'
        'max-width:560px;line-height:1.6">'
        f'One colour spine: <b style="color:{_OK}">green</b> = within line, '
        f'<b style="color:{_MUT}">grey</b> = neutral character, '
        f'<b style="color:{_AMBER}">amber</b> = look here. '
        "Petrol is the only data colour. Hover any <b>i</b> for a definition.</p>"
        '<div class="adr" style="font-family:\'IBM Plex Mono\',monospace;'
        "font-size:10px;letter-spacing:.12em;"
        f'color:{_FAINT};text-transform:uppercase;margin:6px 0 16px">'
        "heuristic surfacing dials &nbsp;&middot;&nbsp; not validated edges</div>"
    )


def _status_banner(flags: list[str]) -> str:
    n = len(flags)
    if n == 0:
        css_class = "risk-status ok"
        icon = "&#10003;"
        label = "All clear"
        headline = "All clear &#8212; nothing crossing a line"
        detail = (
            "All defined risk lines are within threshold. "
            "Your risk character is your choice &#8212; nothing here is &#8220;good&#8221; or &#8220;bad&#8221;."
        )
    else:
        css_class = "risk-status"
        icon = str(n)
        label = "Needs a look"
        _tip = tooltip("Risk line", "ⓘ")
        if n == 1:
            headline = f"1 of your risk line {_tip} is crossed"
        else:
            headline = f"{n} of your risk lines {_tip} are crossed"
        # Build dynamic flag list (no forbidden words)
        _shorts = [_flag_short(f) for f in flags]
        if n == 1:
            _flag_copy = f"One defined line tripped: <b>{_shorts[0]}</b>. Confirm it is intentional."
        elif n == 2:
            _flag_copy = (
                f"Two defined lines tripped: <b>{_shorts[0]}</b> and an"
                f" <b>{_shorts[1]}</b>. Confirm both are intentional."
            )
        else:
            _joined = (
                ", ".join(f"<b>{s}</b>" for s in _shorts[:-1])
                + f" and <b>{_shorts[-1]}</b>"
            )
            _flag_copy = (
                f"{n} defined lines tripped: {_joined}. Confirm all are intentional."
            )
        detail = (
            "Your risk <i>character</i> is your choice &#8212; nothing here is &#8220;good&#8221; or &#8220;bad&#8221;. "
            + _flag_copy
        )

    return (
        f'<div class="{css_class}">'
        f'<div class="risk-big" style="width:46px;height:46px;border-radius:12px;'
        "flex-shrink:0;display:flex;align-items:center;justify-content:center;"
        f"font-family:'Fraunces',serif;font-weight:900;font-size:22px;"
        f'background:{"var(--risk-ok,#15803d)" if n==0 else "var(--risk-amber,#b45309)"};'
        f'color:#fff">{icon}</div>'
        '<div class="risk-st" style="flex:1">'
        f'<div class="risk-sk" style="font-family:\'IBM Plex Mono\',monospace;'
        "font-size:10px;letter-spacing:.12em;text-transform:uppercase;"
        f'color:{"var(--risk-ok,#15803d)" if n==0 else "var(--risk-amber,#b45309)"};'
        f'font-weight:600">{label}</div>'
        f'<div class="risk-sv" style="font-family:\'Fraunces\',serif;font-size:18px;'
        f'font-weight:700;line-height:1.3;margin-top:2px">{headline}</div>'
        f'<div class="risk-ss" style="font-size:12px;color:var(--risk-mut,#5b7178);'
        f'margin-top:3px;line-height:1.45">{detail}</div>'
        "</div>"
        '<div class="risk-meas" style="font-family:\'IBM Plex Mono\',monospace;'
        f"font-size:9px;color:{_FAINT};letter-spacing:.06em;text-align:right;"
        'flex-shrink:0;line-height:1.6">'
        "MEASURED VS<br>&middot;&nbsp;THE MARKET (&beta;=1.0)"
        "<br>&middot;&nbsp;YOUR RISK LINES"
        "<br>&middot;&nbsp;LAST WEEK</div>"
        "</div>"
    )


def _flag_short(flag: str) -> str:
    """Short plain-text description of a flag (no forbidden words)."""
    _MAP = {
        "SYSTEMATIC_DOMINANT": "concentration over 60%",
        "FACTOR_DOMINANCE": "factor dominance",
        "DRIFT": "upward drift",
    }
    return _MAP.get(flag, flag.lower().replace("_", " "))


def _contract_legend() -> str:
    return (
        '<div class="risk-contract" style="background:var(--risk-card,#fff);'
        "border:1px solid var(--risk-line,#dde7e9);border-radius:12px;"
        'padding:11px 14px;margin-bottom:6px">'
        "<div style=\"font-family:'IBM Plex Mono',monospace;font-size:9px;"
        f"letter-spacing:.12em;text-transform:uppercase;color:{_FAINT};"
        'margin-bottom:8px">The whole page in three colours</div>'
        '<div style="display:flex;gap:16px;flex-wrap:wrap">'
        f'<div style="display:flex;align-items:center;gap:6px;font-size:11px;color:{_MUT}">'
        f'<span style="width:12px;height:12px;border-radius:3px;flex-shrink:0;background:{_OK}"></span>'
        f'<b style="color:{_INK}">Green</b> = within your lines</div>'
        f'<div style="display:flex;align-items:center;gap:6px;font-size:11px;color:{_MUT}">'
        f'<span style="width:12px;height:12px;border-radius:3px;flex-shrink:0;'
        f'background:linear-gradient(90deg,{_G2},{_G0},{_G2})"></span>'
        f'<b style="color:{_INK}">Grey</b> = neutral character (no good/bad)</div>'
        f'<div style="display:flex;align-items:center;gap:6px;font-size:11px;color:{_MUT}">'
        f'<span style="width:12px;height:12px;border-radius:3px;flex-shrink:0;background:{_AMBER}"></span>'
        f'<b style="color:{_INK}">Amber</b> = a line crossed &middot; look here</div>'
        f'<div style="display:flex;align-items:center;gap:6px;font-size:11px;color:{_MUT}">'
        f'<span style="width:12px;height:12px;border-radius:3px;flex-shrink:0;background:{_PETROL}"></span>'
        f'<b style="color:{_INK}">Petrol</b> = your exposures (data)</div>'
        "</div></div>"
    )


def _vitals(macro: dict[str, Any]) -> str:
    """Five vital-sign cards: ENB, Net beta, Downside beta, Systematic share, Div ratio."""
    betas: dict[str, float] = macro.get("net_beta_by_factor", {})
    spy_beta = betas.get("SPY")
    sys_share = float(macro.get("systematic_share", 0.0))
    sys_share_adj = float(macro.get("systematic_share_adj", sys_share))
    sys_ci: list[float] = macro.get("systematic_share_ci") or []
    enb = macro.get("enb")
    downside_beta = macro.get("downside_beta")
    div_ratio = macro.get("diversification_ratio")
    total_h = macro.get("total_holdings", "?")

    # Determine amber/grey flags
    sys_over = sys_share >= 0.60

    cards = []

    # ENB
    if enb is not None:
        enb_color = "amber" if float(enb) < 4.0 else "ok"
        cards.append(
            f'<div class="risk-vit {enb_color}">'
            f'<div class="risk-vk">{tooltip("Effective bets")}</div>'
            f'<div class="risk-vv">{enb:.1f}<small> / {total_h}</small></div>'
            f'<div class="risk-vs">{total_h} names, ~{enb:.0f} independent bets</div>'
            "</div>"
        )
    else:
        cards.append(
            f'<div class="risk-vit grey">'
            f'<div class="risk-vk">{tooltip("Effective bets")}</div>'
            f'<div class="risk-vv" style="font-size:14px;color:{_FAINT}">DATA-GAP</div>'
            f'<div class="risk-vs">run weekly-brief to populate</div>'
            "</div>"
        )

    # Net beta (SPY)
    if spy_beta is not None:
        ci_list: list[float] = macro.get("beta_ci_by_factor", {}).get("SPY") or []
        ci_text = f"±{(ci_list[1]-ci_list[0])/2:.2f}" if len(ci_list) == 2 else ""
        cards.append(
            f'<div class="risk-vit grey">'
            f'<div class="risk-vk">Net beta (SPY)</div>'
            f'<div class="risk-vv">{spy_beta:.2f}<small>&times;</small></div>'
            f'<div class="risk-vs">{ci_text}&nbsp;&middot; grey = no line</div>'
            "</div>"
        )

    # Downside beta
    if downside_beta is not None:
        cards.append(
            f'<div class="risk-vit grey">'
            f'<div class="risk-vk">{tooltip("Downside beta")}</div>'
            f'<div class="risk-vv">{float(downside_beta):.2f}<small>&times;</small></div>'
            f'<div class="risk-vs">falls harder than it rises</div>'
            "</div>"
        )

    # Systematic share
    ci_note = ""
    if len(sys_ci) == 2:
        ci_note = f" &plusmn;{(sys_ci[1]-sys_ci[0])/2*100:.0f}"
    sys_card_class = "amber" if sys_over else "grey"
    cards.append(
        f'<div class="risk-vit {sys_card_class}">'
        f'<div class="risk-vk">{tooltip("Systematic share")}</div>'
        f'<div class="risk-vv">{sys_share:.0%}<small>{ci_note}</small></div>'
        f'<div class="risk-vs">adj. {sys_share_adj:.0%} &middot; '
        f'{"over 60% line" if sys_over else "within line"}</div>'
        "</div>"
    )

    # Diversification ratio
    if div_ratio is not None:
        cards.append(
            f'<div class="risk-vit grey">'
            f'<div class="risk-vk">{tooltip("Diversification ratio")}</div>'
            f'<div class="risk-vv">{float(div_ratio):.1f}<small>&times;</small></div>'
            f'<div class="risk-vs">low = names co-move</div>'
            "</div>"
        )

    return '<div class="risk-vitals">' + "".join(cards) + "</div>"


def _lens_nav() -> str:
    return (
        '<div style="display:flex;gap:8px;flex-wrap:wrap;margin:14px 0 0">'
        f'<a href="#safe" class="ri-lens" style="flex:1;min-width:150px;text-decoration:none;background:{_CARD};'
        f"border:1px solid {_LINE};border-radius:11px;padding:11px 13px;"
        f'border-left:4px solid {_G2}">'
        f"<div style=\"font-family:'Fraunces',serif;font-weight:800;font-size:15px\">Am I safe?</div>"
        f"<div style=\"font-family:'IBM Plex Mono',monospace;font-size:9.5px;"
        f'letter-spacing:.08em;text-transform:uppercase;color:{_MUT};margin-top:3px">'
        "The standing &darr;</div></a>"
        f'<a href="#do" class="ri-lens" style="flex:1;min-width:150px;text-decoration:none;background:{_CARD};'
        f"border:1px solid {_LINE};border-radius:11px;padding:11px 13px;"
        f'border-left:4px solid {_AMBER}">'
        f"<div style=\"font-family:'Fraunces',serif;font-weight:800;font-size:15px\">What do I do?</div>"
        f"<div style=\"font-family:'IBM Plex Mono',monospace;font-size:9.5px;"
        f'letter-spacing:.08em;text-transform:uppercase;color:{_MUT};margin-top:3px">'
        "Dials + drill-downs &darr;</div></a>"
        f'<a href="#teach" class="ri-lens" style="flex:1;min-width:150px;text-decoration:none;background:{_CARD};'
        f"border:1px solid {_LINE};border-radius:11px;padding:11px 13px;"
        f'border-left:4px solid {_PETROL}">'
        f"<div style=\"font-family:'Fraunces',serif;font-weight:800;font-size:15px\">Teach me</div>"
        f"<div style=\"font-family:'IBM Plex Mono',monospace;font-size:9.5px;"
        f'letter-spacing:.08em;text-transform:uppercase;color:{_MUT};margin-top:3px">'
        "Story + Google AI &darr;</div></a>"
        "</div>"
    )


def _standing(macro: dict[str, Any]) -> str:
    betas: dict[str, float] = macro.get("net_beta_by_factor", {})
    spy_beta = betas.get("SPY", 0.0)
    sys_share = float(macro.get("systematic_share", 0.0))
    sys_over = sys_share >= 0.60

    return (
        '<div class="ri-sec" id="safe">Am I safe? &middot; The standing</div>'
        f'<div class="hero" style="background:{_CARD};border:1px solid {_LINE};'
        'border-radius:16px;padding:22px 24px;position:relative;overflow:hidden">'
        f'<div style="position:absolute;left:0;top:0;bottom:0;width:5px;'
        f'background:linear-gradient({_G1},{_AMBER})"></div>'
        '<div style="display:flex;align-items:center;gap:9px;margin-bottom:13px;flex-wrap:wrap">'
        f"<span style=\"font-family:'IBM Plex Mono',monospace;font-size:11px;"
        f"font-weight:600;letter-spacing:.05em;padding:5px 11px;border-radius:8px;"
        f'background:#eef1f4;color:#334155;border:1px solid #dbe2e8">MARKET-LIKE</span>'
        + (
            f"<span style=\"font-family:'IBM Plex Mono',monospace;font-size:11px;"
            f"font-weight:600;letter-spacing:.05em;padding:5px 11px;border-radius:8px;"
            f'background:{_AMBER};color:#fff;border-color:{_AMBER}">CONCENTRATED &middot; FLAGGED</span>'
            if sys_over
            else "<span style=\"font-family:'IBM Plex Mono',monospace;font-size:11px;"
            "font-weight:600;letter-spacing:.05em;padding:5px 11px;border-radius:8px;"
            'background:#eef1f4;color:#334155;border:1px solid #dbe2e8">DIVERSIFIED</span>'
        )
        + f"<span style=\"font-family:'IBM Plex Mono',monospace;font-size:10px;"
        f'color:{_FAINT};letter-spacing:.06em;margin-left:auto">CHARACTER &middot; NOT A RATING</span>'
        "</div>"
        f"<div style=\"font-family:'Fraunces',serif;font-size:21px;font-weight:700;"
        f'line-height:1.4;letter-spacing:-.01em">'
        f"Your book moves about <b>{spy_beta:.2f}&times;</b> the market &#8212; roughly in step "
        + (
            f'<span style="color:{_AMBER};font-weight:700">(concentration flagged)</span>'
            if sys_over
            else f'<span style="color:{_OK};">(within range)</span>'
        )
        + f'. But <b style="color:{_AMBER if sys_over else _INK}">{sys_share:.0%}</b> '
        "of its swings trace to a "
        f'<b style="color:{_AMBER if sys_over else _INK}">single market-wide bet</b>'
        + (
            f' &#8212; past the 60% line, so it\'s <b style="color:{_AMBER}">flagged</b>.'
            if sys_over
            else " &#8212; within the 60% line."
        )
        + "</div>"
        f'<div style="margin-top:14px;background:#f7fafb;border:1px solid {_LINE};'
        f"border-left:4px solid {_G1};border-radius:9px;padding:12px 14px;"
        f'font-size:13.5px;line-height:1.6;color:#33474c">'
        "Translation: the <b>size</b> of your market exposure is a normal choice. "
        + (
            "What tripped a line is the <b>concentration</b>: too much riding on one bet. "
            "That's the part to confirm you meant."
            if sys_over
            else "Both the size and concentration are within defined lines."
        )
        + "</div></div>"
    )


def _dials(macro: dict[str, Any]) -> str:
    """Three gauge dials: Market exposure, Diversification, Concentration."""
    betas: dict[str, float] = macro.get("net_beta_by_factor", {})
    spy_beta = betas.get("SPY", 0.0)
    sys_share = float(macro.get("systematic_share", 0.0))
    idio_share = max(0.0, 1.0 - sys_share)
    sys_over = sys_share >= 0.60

    # Needle rotation helpers (-90 = left edge, +90 = right edge)
    def _rot(val: float, lo: float, hi: float) -> float:
        pct = max(0.0, min(1.0, (val - lo) / max(hi - lo, 1e-9)))
        return (pct - 0.5) * 180.0

    beta_rot = _rot(spy_beta, 0.0, 2.0)
    idio_rot = _rot(idio_share, 0.0, 1.0)
    conc_rot = _rot(sys_share, 0.0, 1.0)

    def _dial_svg(rot: float, c1: str, c2: str, c3: str, p1: str, p2: str) -> str:
        return (
            f'<div class="dial" style="width:120px;height:60px;margin:0 auto;'
            'position:relative;overflow:hidden">'
            f'<div style="width:120px;height:120px;border-radius:50%;'
            f'background:conic-gradient(from 270deg,{c1} 0 {p1},{c2} {p1} {p2},{c3} {p2} 50%,transparent 50% 100%)"></div>'
            '<div style="position:absolute;left:13px;top:13px;width:94px;height:94px;'
            'border-radius:50%;background:#fff"></div>'
            f'<div style="position:absolute;left:50%;bottom:0;width:2.5px;height:52px;'
            f"background:{_INK};transform-origin:bottom center;border-radius:2px;"
            f'transform:translateX(-50%) rotate({rot:.0f}deg)"></div>'
            "</div>"
        )

    # Gauge 1: Market exposure — green (no line), grey arc
    gauge1 = (
        f'<div class="risk-gauge clear">'
        f'<div class="risk-glab">{tooltip("Net beta", "Market exposure")}</div>'
        + _dial_svg(beta_rot, _G0, _G1, _G2, "30%", "40%")
        + f'<div class="risk-gval">{spy_beta:.2f}&times;</div>'
        f'<div class="risk-gband ok">No line crossed</div>'
        f'<div class="risk-gsub">1.0 = market &middot; {abs(spy_beta-1):.0%} above</div>'
        "</div>"
    )

    # Gauge 2: Diversification — grey, character only
    idio_pct = f"{idio_share:.0%}"
    gauge2 = (
        f'<div class="risk-gauge">'
        f'<div class="risk-glab">{tooltip("Diversification ratio", "Diversification")}</div>'
        + _dial_svg(idio_rot, _G2, _G1, _G0, "25%", "40%")
        + f'<div class="risk-gval">{idio_pct}</div>'
        f'<div class="risk-gband">Character only</div>'
        f'<div class="risk-gsub">{idio_pct} of risk is stock-specific</div>'
        "</div>"
    )

    # Gauge 3: Concentration — amber if flagged
    conc_class = "risk-gauge flagged" if sys_over else "risk-gauge"
    conc_gband = (
        '<div class="risk-gband warn">Over 60% line</div>'
        if sys_over
        else '<div class="risk-gband">Within line</div>'
    )
    gauge3 = (
        f'<div class="{conc_class}">'
        f'<div class="risk-glab">{tooltip("Systematic share", "Concentration")}</div>'
        + _dial_svg(conc_rot, _G1, "#d8b27a", _AMBER, "30%", "40%")
        + f'<div class="risk-gval" style="color:{"var(--risk-amber)" if sys_over else _INK}">'
        f"{sys_share:.0%}</div>"
        + conc_gband
        + '<div class="risk-gsub">one factor drives most of it</div>'
        "</div>"
    )

    return (
        '<div class="ri-sec" id="do" style="color:var(--risk-amber)">'
        "What do I do? &middot; The dials</div>"
        '<div class="risk-cluster">' + gauge1 + gauge2 + gauge3 + "</div>"
        '<div class="risk-spectrum-note">'
        "&#9650; GREY = CHARACTER (NO GOOD/BAD) &middot; "
        "GREEN = NO LINE &middot; AMBER = FLAGGED. "
        "SIZE ISN'T GRADED &#8212; ONLY DEFINED LINES ARE. "
        "positions on a spectrum, not scores"
        "</div>"
    )


def _grill_drill(flags: list[str]) -> str:
    if not flags:
        return ""
    return (
        '<details class="drill" style="margin-top:13px;border:1px solid var(--risk-amber-b);'
        'border-radius:13px;background:var(--risk-card);overflow:hidden" open>'
        '<summary style="list-style:none;cursor:pointer;padding:13px 16px;'
        "display:flex;align-items:center;gap:10px;font-size:13px;color:#5b4a28;"
        'background:linear-gradient(120deg,var(--risk-amber-l),#fff 80%)">'
        "<span style=\"font-family:'IBM Plex Mono',monospace;color:var(--risk-amber)\">&#9658;</span>"
        "<b style=\"font-family:'IBM Plex Mono',monospace;font-size:11px;"
        'letter-spacing:.06em;color:var(--risk-amber)">GRILL INTO THE FLAG &#8212;</b>'
        "&nbsp; concentration is over the 60% line. What needs attention?"
        "</summary>"
        '<div style="padding:14px 16px;border-top:1px solid var(--risk-amber-b);'
        'font-size:12.5px;line-height:1.6;color:#33474c">'
        '<div style="display:flex;gap:11px;align-items:flex-start;font-size:13px;'
        'line-height:1.5;color:#33474c;margin-bottom:9px">'
        '<span style="flex-shrink:0;width:22px;height:22px;border-radius:6px;'
        "background:var(--risk-amber);color:#fff;font-family:'IBM Plex Mono';"
        "font-weight:700;font-size:11px;display:flex;align-items:center;"
        'justify-content:center;margin-top:1px">1</span>'
        "<div><b>Adding another large-cap tech name won't clear it.</b> "
        "Same bet &#8594; concentration stays &gt;60%. Only a different asset class or hedge moves it.</div>"
        "</div>"
        '<div style="display:flex;gap:11px;align-items:flex-start;font-size:13px;'
        'line-height:1.5;color:#33474c;margin-bottom:9px">'
        '<span style="flex-shrink:0;width:22px;height:22px;border-radius:6px;'
        "background:var(--risk-amber);color:#fff;font-family:'IBM Plex Mono';"
        "font-weight:700;font-size:11px;display:flex;align-items:center;"
        'justify-content:center;margin-top:1px">2</span>'
        "<div><b>Decide if the concentration is intentional.</b> "
        "Fine if you chose a market bet; a gap if you assumed diversification.</div>"
        "</div>"
        '<div style="display:flex;gap:11px;align-items:flex-start;font-size:13px;'
        'line-height:1.5;color:#33474c">'
        '<span style="flex-shrink:0;width:22px;height:22px;border-radius:6px;'
        "background:var(--risk-amber);color:#fff;font-family:'IBM Plex Mono';"
        "font-weight:700;font-size:11px;display:flex;align-items:center;"
        'justify-content:center;margin-top:1px">3</span>'
        "<div><b>The drivers are concrete</b> &#8212; see Who owns the bet + sector breakdown below. "
        "Trimming the biggest risk contributors clears the flag fastest.</div>"
        "</div>"
        "</div></details>"
    )


def _evidence_bands(macro: dict[str, Any]) -> str:
    """Net-beta grey distance ramp + systematic-share strip with CI band."""
    betas: dict[str, float] = macro.get("net_beta_by_factor", {})
    spy_beta = betas.get("SPY")
    sys_share = float(macro.get("systematic_share", 0.0))
    sys_share_adj = float(macro.get("systematic_share_adj", sys_share))
    sys_ci: list[float] = macro.get("systematic_share_ci") or []
    sys_over = sys_share >= 0.60

    if spy_beta is None:
        return (
            '<div class="ri-sec">The evidence &#8212; where you sit</div>'
            '<div class="bands" style="background:var(--risk-card);border:1px solid var(--risk-line);'
            'border-radius:14px;padding:18px 20px">'
            f'<p style="font-size:12px;color:{_MUT}">DATA-GAP: net beta not available &#8212; '
            "run weekly-brief to populate.</p></div>"
        )

    # ── Beta strip ──────────────────────────────────────────────────────────
    beta_needle = _strip_pct(spy_beta, _BETA_DOMAIN_LO, _BETA_DOMAIN_HI)
    beta_band = classify_net_beta(spy_beta)
    beta_label = beta_band.value

    beta_strip = (
        '<div style="margin-bottom:22px">'
        "<div style=\"font-family:'IBM Plex Mono',monospace;font-size:10px;"
        f"letter-spacing:.13em;text-transform:uppercase;color:{_FAINT};"
        'display:flex;justify-content:space-between;margin-bottom:7px">'
        f'<span>{tooltip("Net beta", "Net market beta (SPY)")}</span>'
        f'<span style="color:{_INK};font-weight:600">+{spy_beta:.2f} &middot; {beta_label} '
        f"<span style=\"font-family:'IBM Plex Mono',monospace;font-size:9px;"
        f"font-weight:600;padding:1px 7px;border-radius:6px;margin-left:7px;"
        f'background:{_OK};color:#fff">no line</span></span>'
        "</div>"
        '<div style="position:relative;height:14px;border-radius:7px;display:flex;'
        'box-shadow:inset 0 0 0 1px rgba(0,0,0,.03)">'
        # 5 grey ramp segments (symmetric — distance from 1.0 market)
        f'<div style="width:20%;background:{_G2};height:100%;border-radius:7px 0 0 7px"></div>'
        f'<div style="width:32%;background:{_G1};height:100%"></div>'
        f'<div style="width:16%;background:{_G0};height:100%"></div>'
        f'<div style="width:16%;background:{_G1};height:100%"></div>'
        f'<div style="width:16%;background:{_G2};height:100%;border-radius:0 7px 7px 0"></div>'
        # market reference tick at 60% position (1.0 on -0.5..2.0 scale)
        f'<div style="position:absolute;top:-3px;width:2px;height:20px;background:{_INK};left:60%"></div>'
        # needle
        f'<div style="position:absolute;top:-5px;width:3px;height:24px;background:{_INK};'
        f'border-radius:2px;box-shadow:0 0 0 2px #fff;left:{beta_needle:.1f}%"></div>'
        "</div>"
        '<div style="display:flex;justify-content:space-between;'
        f"font-family:'IBM Plex Mono',monospace;font-size:9.5px;color:{_FAINT};margin-top:6px\">"
        "<span>&#8722;0.5 hedged</span>"
        f'<span style="color:{_INK}">1.0 market</span>'
        "<span>2.0 aggressive</span>"
        "</div>"
        "</div>"
    )

    # ── Systematic-share strip with CI band ────────────────────────────────
    share_needle = sys_share * 100.0
    share_over_class = f"color:{_AMBER}" if sys_over else f"color:{_INK}"
    share_tag_style = (
        f"background:{_AMBER};color:#fff"
        if sys_over
        else f"background:{_OK};color:#fff"
    )
    share_tag_text = "over 60% line" if sys_over else "within line"

    # CI band coordinates
    ci_band_html = ""
    ci_label_html = ""
    if len(sys_ci) == 2:
        ci_lo_pct = sys_ci[0] * 100.0
        ci_hi_pct = sys_ci[1] * 100.0
        ci_width = ci_hi_pct - ci_lo_pct
        ci_band_html = f'<div class="risk-ciband" style="left:{ci_lo_pct:.1f}%;width:{ci_width:.1f}%"></div>'
        ci_label_html = (
            '<div class="risk-cilabel">'
            f"shaded = 90% bootstrap range ({sys_ci[0]:.0%}&#8211;{sys_ci[1]:.0%}); "
            "even the low end clears the 60% line"
            "</div>"
        )

    # Build the systematic-share strip:
    ci_badge = ""
    if len(sys_ci) == 2:
        ci_badge = (
            f" <small style=\"font-family:'IBM Plex Mono';font-weight:500;color:{_MUT}\">"
            f"&plusmn;{(sys_ci[1]-sys_ci[0])/2*100:.0f}% &middot; adj {sys_share_adj:.0%}</small>"
        )

    share_strip_final = (
        '<div style="margin-bottom:0">'
        "<div style=\"font-family:'IBM Plex Mono',monospace;font-size:10px;"
        f"letter-spacing:.13em;text-transform:uppercase;color:{_FAINT};"
        'display:flex;justify-content:space-between;margin-bottom:7px">'
        f'<span>{tooltip("Systematic share", "Systematic share of risk")}</span>'
        f'<span style="{share_over_class};font-weight:600">'
        f"{sys_share:.0%}{ci_badge} "
        f"<span style=\"font-family:'IBM Plex Mono',monospace;font-size:9px;"
        f"font-weight:600;padding:1px 7px;border-radius:6px;margin-left:7px;"
        f'{share_tag_style}">{share_tag_text}</span>'
        "</span></div>"
        '<div style="position:relative;height:14px;border-radius:7px;display:flex;'
        'box-shadow:inset 0 0 0 1px rgba(0,0,0,.03)">'
        f'<div style="width:40%;background:{_OK};height:100%;border-radius:7px 0 0 7px"></div>'
        '<div style="width:20%;background:#86C7A1;height:100%"></div>'
        '<div style="width:15%;background:#E0A33E;height:100%"></div>'
        f'<div style="width:25%;background:{_AMBER};height:100%;border-radius:0 7px 7px 0"></div>'
        # amber hatch over-zone
        f'<div style="position:absolute;top:0;height:14px;'
        "background:repeating-linear-gradient(45deg,rgba(180,83,9,.30),rgba(180,83,9,.30) 4px,"
        "rgba(180,83,9,.12) 4px,rgba(180,83,9,.12) 8px);"
        f'border-left:2px solid {_AMBER};left:{_SHARE_FLAG_PCT:.0f}%;width:{100-_SHARE_FLAG_PCT:.0f}%"></div>'
        # flag line
        f'<div style="position:absolute;top:-3px;width:2px;height:20px;background:{_AMBER};'
        f'left:{_SHARE_FLAG_PCT:.0f}%"></div>'
        # CI band
        + ci_band_html +
        # needle
        f'<div style="position:absolute;top:-5px;width:3px;height:24px;'
        f"background:{_AMBER if sys_over else _INK};"
        f'border-radius:2px;box-shadow:0 0 0 2px #fff;left:{share_needle:.1f}%"></div>'
        "</div>"
        + ci_label_html
        + '<div style="display:flex;justify-content:space-between;'
        f"font-family:'IBM Plex Mono',monospace;font-size:9.5px;color:{_FAINT};margin-top:6px\">"
        f'<span style="color:{_OK}">0% diversified</span>'
        f"<span style=\"display:inline-block;font-family:'IBM Plex Mono',monospace;"
        f"font-size:9.5px;font-weight:600;padding:1px 7px;border-radius:6px;"
        f'background:{_AMBER};color:#fff">60% flag line</span>'
        f'<span style="color:{_AMBER}">100% all macro</span>'
        "</div>"
        "</div>"
    )

    return (
        '<div class="ri-sec">The evidence &#8212; where you sit</div>'
        f'<div class="bands" style="background:{_CARD};border:1px solid {_LINE};'
        'border-radius:14px;padding:18px 20px">'
        f'<p class="bcap" style="font-size:12px;color:{_MUT};line-height:1.55;margin:0 0 16px">'
        "Grey ramp = how far you sit from &#8220;market-like&#8221; &#8212; same shade both "
        "directions, because distance is not good or bad. "
        "The amber hatch marks the one line you&#8217;ve crossed. "
        "Shaded band = 90% bootstrap range around the needle.</p>"
        + beta_strip
        + share_strip_final
        + "</div>"
    )


# ---------------------------------------------------------------------------
# Factor display-name map: ticker → (short subtitle for display under ticker)
# Covers the 4 live factors; falls back to bare ticker for any unknown factor.
# ---------------------------------------------------------------------------
_FACTOR_DISPLAY_NAMES: dict[str, str] = {
    "SPY": "Market",
    "TLT": "Rates 10Y",
    "UUP": "US Dollar",
    "XLE": "Energy",
    # common extended-universe proxies (for future expansion)
    "IWM": "Small Caps",
    "HYG": "Credit HYG",
    "GLD": "Gold",
    "USO": "Oil WTI",
    "QQQ": "Nasdaq",
    "IWD": "Value HML",
    "MTUM": "Momentum",
    "VLUE": "Value HML",
}


def _factor_chart(macro: dict[str, Any]) -> str:
    """Diverging petrol bars for configured factors with whiskers + VIF note."""
    betas: dict[str, float] = macro.get("net_beta_by_factor", {})
    if not betas:
        return (
            '<div class="ri-sec">What\'s driving it &middot; factors</div>'
            f'<div class="barwrap" style="background:{_CARD};border:1px solid {_LINE};'
            f'border-radius:14px;padding:18px 20px">'
            f'<p style="font-size:12px;color:{_MUT}">DATA-GAP: no factor betas available.</p>'
            "</div>"
        )

    ci_by_factor: dict[str, list[float]] = macro.get("beta_ci_by_factor") or {}
    suppressed: list[str] = macro.get("suppressed_factors") or []
    vif: dict[str, Any] = macro.get("vif_by_factor") or {}
    dominant_factor: str = macro.get("dominant_factor") or ""

    n_factors = len(betas)

    # Determine display range for diverging track
    max_abs = max(abs(v) for v in betas.values()) if betas else 1.0
    domain = max(max_abs * 1.2, 0.3)  # ensure we have some range

    # Build VIF note for collinear factors
    high_vif_factors = [
        f
        for f, v in vif.items()
        if (v is None or (isinstance(v, (int, float)) and v > 5))
    ]
    vif_note = ""
    if high_vif_factors:
        vif_note = (
            f'<p style="font-size:11px;color:{_MUT};margin:0 0 12px">'
            f'&#9888; {", ".join(_html.escape(f) for f in high_vif_factors)} are <b>collinear</b> '
            f'({tooltip("VIF")}&nbsp;&gt;&nbsp;5) &#8212; '
            "read them as <b>one growth-market cluster</b>, not separate bets. "
            "The whiskers widen because of this overlap.</p>"
        )

    rows = ""
    for factor, beta_val in betas.items():
        is_suppressed = factor in suppressed
        ci = ci_by_factor.get(factor) or []

        # centre pin at 40% of track; right=long, left=short
        centre = 40.0
        scale = 40.0 / domain  # 40% of width per unit

        is_long = beta_val >= 0.0
        bar_width = abs(beta_val) * scale
        if is_long:
            bar_left = centre
        else:
            bar_left = centre - bar_width

        # Suppressed = CI straddles zero → grey out
        bar_style = (
            "background:#cdd6d6;border-color:#cdd6d6"
            if is_suppressed
            else (
                f"background:{_PETROL_L};border:1.5px solid {_PETROL}"
                if not is_long
                else f"background:{_PETROL}"
            )
        )

        # Whisker
        whisk_html = ""
        if len(ci) == 2:
            ci_lo = float(ci[0])
            ci_hi = float(ci[1])
            # map ci lo/hi to % positions
            wlo = centre + ci_lo * scale
            whi = centre + ci_hi * scale
            if wlo > whi:
                wlo, whi = whi, wlo
            w_left = max(0.0, wlo)
            w_width = max(0.0, whi - wlo)
            whisk_html = f'<div class="risk-whisk" style="left:{w_left:.1f}%;width:{w_width:.1f}%"></div>'

        # Label for dominant factor — exactly one label per factor, in priority order:
        #   suppressed (CI straddles 0) → ≈0
        #   short (negative beta, not suppressed) → SHORT
        #   dominant (factor == macro["dominant_factor"]) → DOMINANT
        #   otherwise → no label
        if is_suppressed:
            dom_label = (
                "<span style=\"font-family:'IBM Plex Mono',monospace;font-size:8px;"
                "font-weight:700;background:#eef1f4;color:var(--risk-faint);"
                'padding:1px 5px;border-radius:5px">≈0</span>'
            )
        elif not is_long:
            dom_label = (
                f"<span style=\"font-family:'IBM Plex Mono',monospace;font-size:8px;"
                f"font-weight:700;background:{_PETROL_L};color:{_PETROL_D};"
                f'padding:1px 5px;border-radius:5px;border:1px solid #bfe0e6">SHORT</span>'
            )
        elif dominant_factor and factor == dominant_factor:
            dom_label = (
                f"<span style=\"font-family:'IBM Plex Mono',monospace;font-size:8px;"
                f"font-weight:700;background:{_PETROL};color:#fff;"
                'padding:1px 5px;border-radius:5px;letter-spacing:.05em">DOMINANT</span>'
            )
        else:
            dom_label = ""

        # Factor display subtitle (e.g. "Market" for SPY)
        subtitle = _FACTOR_DISPLAY_NAMES.get(factor, "")
        subtitle_html = (
            f'<span style="font-size:9.5px;font-weight:400;color:{_FAINT};margin-left:3px">'
            f"{_html.escape(subtitle)}</span>"
            if subtitle
            else ""
        )

        row_class = "frow supp" if is_suppressed else "frow"
        name_color = _FAINT if is_suppressed else _INK
        val_color = _FAINT if is_suppressed else _INK

        rows += (
            f'<div class="{row_class}" style="display:grid;grid-template-columns:128px 1fr 50px;'
            'gap:10px;align-items:center;font-size:11.5px;margin-bottom:9px">'
            f"<span style=\"font-family:'IBM Plex Mono',monospace;color:{name_color};"
            'display:flex;align-items:center;gap:6px;flex-wrap:wrap">'
            f"{_html.escape(factor)}{subtitle_html}&nbsp;{dom_label}</span>"
            f'<div style="position:relative;height:14px;border-radius:4px;background:#f4f7f8">'
            '<div style="position:absolute;left:40%;top:-3px;bottom:-3px;width:1.5px;background:#b6c2c2"></div>'
            f'<div style="position:absolute;top:3px;height:8px;border-radius:3px;'
            f'left:{bar_left:.1f}%;width:{bar_width:.1f}%;{bar_style}"></div>'
            + whisk_html
            + "</div>"
            f"<span style=\"font-family:'IBM Plex Mono',monospace;text-align:right;"
            f'color:{val_color}">'
            f"{beta_val:+.2f}</span>"
            "</div>"
        )

    axis_lo = -round(domain, 1)
    axis_hi = round(domain, 1)

    # --- READ summary line (dynamically generated from live macro) ---
    long_factors = [f for f, v in betas.items() if v > 0.0 and f not in suppressed]
    short_factors = [f for f, v in betas.items() if v < 0.0 and f not in suppressed]
    suppressed_non_dominant = [f for f in suppressed if f != dominant_factor]

    def _factor_label(f: str) -> str:
        sub = _FACTOR_DISPLAY_NAMES.get(f, "")
        return f"{f} ({sub})" if sub else f

    dom_label_str = _factor_label(dominant_factor) if dominant_factor else ""

    read_parts: list[str] = []
    if long_factors:
        long_names = ", ".join(_factor_label(f) for f in long_factors)
        read_parts.append(f"long {long_names}")
    if short_factors:
        short_names = ", ".join(_factor_label(f) for f in short_factors)
        read_parts.append(f"short {short_names}")
    if suppressed_non_dominant:
        supp_names = ", ".join(_factor_label(f) for f in suppressed_non_dominant)
        read_parts.append(f"{supp_names} near zero (not distinguishable from no tie)")

    read_body = "; ".join(read_parts) if read_parts else "no active factor exposures"

    dom_note = ""
    if dom_label_str:
        dom_note = f" {_html.escape(dom_label_str)} dwarfs the rest &#8212; that&#8217;s why concentration is flagged."

    read_html = f"<b>READ:</b> {_html.escape(read_body)}.{dom_note}"

    # --- Combined .fnote block: READ + whisker footnote ---
    fnote_html = (
        f"<div style=\"font-family:'IBM Plex Mono',monospace;font-size:10px;color:{_FAINT};"
        'margin-top:12px;border-top:1px dashed var(--risk-line);padding-top:9px;line-height:1.6">'
        + read_html
        + "<br>The thin whiskers are <b>90% confidence intervals</b>; greyed factors have "
        "an interval that straddles zero &#8212; not distinguishable from &#8220;no tie&#8221;, "
        "so we don&#8217;t pretend they&#8217;re real."
        "</div>"
    )

    return (
        f'<div class="ri-sec">What\'s driving it &middot; {n_factors} factors</div>'
        f'<div class="barwrap" style="background:{_CARD};border:1px solid {_LINE};'
        'border-radius:14px;padding:18px 20px">'
        f'<p class="bcap2" style="font-size:12px;color:{_MUT};line-height:1.55;margin:0 0 12px">'
        "Bars point <b>right</b> when the book moves <b>with</b> a factor "
        "(long, solid petrol), <b>left</b> when it moves <b>against</b> it "
        "(short / hedge, hollow). Length = strength of the tie.<br>" + vif_note + "</p>"
        '<div style="display:grid;grid-template-columns:128px 1fr 50px;gap:10px;'
        f"font-family:'IBM Plex Mono',monospace;font-size:9px;"
        f'letter-spacing:.08em;text-transform:uppercase;color:{_FAINT};margin:0 0 8px">'
        "<span>Factor</span><span>&larr; short &nbsp;&middot;&nbsp; long &rarr;</span>"
        '<span style="text-align:right">Net &beta;</span></div>'
        + rows
        + f'<div style="display:flex;justify-content:space-between;'
        f"font-family:'IBM Plex Mono',monospace;font-size:9px;color:{_FAINT};"
        'margin-top:2px;padding-left:138px">'
        f"<span>{axis_lo:.1f}</span>"
        f'<span style="position:relative;left:-12px">0 (no tie)</span>'
        f"<span>+{axis_hi:.1f}</span>"
        "</div>" + fnote_html + "</div>"
    )


def _enb_section(macro: dict[str, Any]) -> str:
    """ENB block + expandable drill-down: named bets + how-to-raise."""
    enb = macro.get("enb")
    pc_variance: list[float] = macro.get("pc_variance") or []
    pc_labels: list[str] = macro.get("pc_labels") or []
    pc_gap: bool = bool(macro.get("pc_labels_data_gap", False))
    total_h = macro.get("total_holdings", "?")
    sector_gaps: list[str] = macro.get("sector_gaps") or []

    if enb is None:
        return (
            '<div class="ri-sec">How many real bets?</div>'
            '<div class="risk-enb">'
            '<p style="font-size:12.5px;color:#33474c">DATA-GAP: effective bets not available &#8212; '
            "run weekly-brief to populate.</p>"
            "</div>"
        )

    # Degenerate-covariance guard: enb may be 0.0 with no pc_variance when the
    # portfolio has too few history points for a meaningful decomposition.
    # Treat this the same as the data-gap case rather than crashing on pc_variance[0].
    if not pc_variance:
        return (
            f'<div class="ri-sec">How many real bets? {tooltip("Effective bets")}</div>'
            '<div class="risk-enb">'
            f'<div class="risk-enbnum">'
            f'<div class="risk-big-n">{enb:.1f}</div>'
            f'<div class="risk-of">of {total_h} names</div>'
            '<div class="risk-lab">Effective bets</div>'
            "</div>"
            '<div class="risk-enbright">'
            f'<p style="font-size:12.5px;color:#33474c">DATA-GAP: not enough price history to '
            "decompose bets &#8212; run weekly-brief once more history is available. "
            "The effective-bets count is shown but variance attribution requires more data.</p>"
            "</div></div>"
        )

    # Build PC variance bars (top 3 + residual).
    # The use case truncates pc_variance to the top-3 eigenvalue shares, so we
    # compute the residual as the variance NOT captured by the shown components
    # rather than summing the (always-empty) tail pc_variance[3:].
    top3 = (
        list(zip(pc_variance[:3], pc_labels[:3])) if pc_variance and pc_labels else []
    )
    rest_variance = max(0.0, 1.0 - sum(pc_variance))
    max_pc = max(pc_variance[:3]) if pc_variance else 1.0

    pc_rows = ""
    for i, (var, lbl) in enumerate(top3):
        pct_of_max = var / max_pc * 100.0 if max_pc > 0 else 0.0
        row_name = f"PC-{i+1}"
        fill_class = "risk-pf one" if i == 0 else "risk-pf"
        pc_rows += (
            f'<div class="risk-pcrow">'
            f'<span class="risk-pn">{row_name}</span>'
            f'<span class="risk-pt"><span class="{fill_class}" style="width:{pct_of_max:.0f}%"></span></span>'
            f'<span class="risk-pv">{var:.0%}</span>'
            "</div>"
        )
    if rest_variance > 0:
        pc_rows += (
            '<div class="risk-pcrow">'
            f'<span class="risk-pn">PC 4&#8211;{total_h}</span>'
            f'<span class="risk-pt"><span class="risk-pf" style="width:{rest_variance/max_pc*100:.0f}%;background:#cdd6d6"></span></span>'
            f'<span class="risk-pv">{rest_variance:.0%}</span>'
            "</div>"
        )

    # Build the expandable drill-down
    # Bet names: use labels if not data-gap, else "Bet N"
    def _bet_name(i: int) -> str:
        if pc_gap or i >= len(pc_labels):
            return f"Bet {i+1}"
        return _html.escape(pc_labels[i])

    def _bet_desc(i: int) -> str:
        if pc_gap:
            return ""
        if i == 0:
            return (
                "Your book's largest shared axis. The names loading on it move "
                "together; swapping one for another <i>within</i> this axis does "
                "NOT reduce the bet."
            )
        if i == 1:
            return "A secondary axis &#8212; a genuinely different, smaller source of risk from the dominant one."
        return "A thin idiosyncratic spread &#8212; the only place your stock-picking actually shows up."

    chaps = ""
    for i in range(min(3, len(pc_variance) if pc_variance else 3)):
        var_pct = f"{pc_variance[i]:.0%}" if i < len(pc_variance) else "?"
        name = _bet_name(i)
        desc = _bet_desc(i)
        chaps += (
            f'<div style="padding:11px 0;border-bottom:1px solid #eef3f4">'
            f"<div style=\"font-family:'IBM Plex Mono',monospace;font-size:10px;"
            f'font-weight:600;color:{_AMBER if i==0 else _PETROL};letter-spacing:.1em">'
            f"BET {i+1} &middot; {var_pct} of your risk</div>"
            f"<div style=\"font-family:'Fraunces',serif;font-weight:700;font-size:14px;margin:3px 0 4px\">{name}</div>"
            + (
                f'<p style="font-size:12.5px;line-height:1.55;color:#33474c;margin-top:4px">{desc}</p>'
                if desc
                else ""
            )
            + "</div>"
        )

    # DATA-GAP note
    gap_note = ""
    if pc_gap:
        gap_note = (
            f'<div style="margin-top:8px;background:#f7fafb;border:1px solid {_LINE};'
            f"border-left:4px solid {_G1};border-radius:9px;padding:11px 13px;"
            f'font-size:12px;color:#33474c;line-height:1.55">'
            "<b>DATA-GAP:</b> not enough price history to name the underlying axes. "
            "Showing PCA variance shares only &#8212; the numbers are correct, "
            "the &#8220;what&#8221; behind each bet requires more data. "
            f"<span style=\"font-family:'IBM Plex Mono',monospace;font-size:9px;font-weight:600;"
            "background:#eef1f4;color:var(--risk-mut);padding:1px 6px;border-radius:5px;"
            'letter-spacing:.05em;margin-left:4px">DATA-GAP</span>'
            "</div>"
        )

    # Sector gaps note for "how to raise ENB"
    gaps_text = ""
    if sector_gaps:
        gaps_text = (
            f'<div style="display:flex;gap:11px;align-items:flex-start;font-size:13px;'
            f'line-height:1.5;color:#33474c;margin-bottom:9px">'
            f'<span style="flex-shrink:0;width:22px;height:22px;border-radius:6px;'
            f"background:{_AMBER};color:#fff;font-family:'IBM Plex Mono';"
            "font-weight:700;font-size:11px;display:flex;align-items:center;"
            'justify-content:center;margin-top:1px">&#8593;</span>'
            f"<div><b>Add exposure on an axis you're empty on.</b> "
            f"The book has zero weight in: "
            f'{", ".join(_html.escape(g) for g in sector_gaps)}. '
            "Adding any one loads a new principal portfolio &#8594; ENB rises. "
            f"<span style=\"font-family:'IBM Plex Mono',monospace;font-size:9px;font-weight:600;"
            "background:#eef1f4;color:var(--risk-mut);padding:1px 6px;border-radius:5px;"
            'letter-spacing:.05em">DESCRIPTIVE &middot; NOT A TRADE CALL</span>'
            "</div></div>"
        )

    drill = (
        '<details class="teach" style="border-left-color:var(--risk-amber);margin-top:10px" open>'
        '<summary style="list-style:none;cursor:pointer;padding:14px 17px;'
        f"font-family:'IBM Plex Mono',monospace;font-size:11px;letter-spacing:.1em;"
        f"text-transform:uppercase;color:{_PETROL};font-weight:600;"
        'display:flex;justify-content:space-between;align-items:center">'
        "<span style=\"font-family:'Fraunces',serif;font-weight:700;font-size:15px;"
        f'text-transform:none;color:{_INK}">What are my ~{enb:.0f} bets, and how do I raise it?</span>'
        "<span>&#9660;</span></summary>"
        '<div style="padding:4px 17px 14px">'
        f'<p style="margin:6px 0 12px;font-size:12.5px;line-height:1.55;color:#33474c">'
        f"<b>&#8220;{enb:.1f} effective bets&#8221; means:</b> if you redrew your {total_h} "
        "holdings as a handful of <i>uncorrelated</i> wagers, you'd have about "
        f"{enb:.0f}. Names aren&#8217;t bets &#8212; <b>independent risks</b> are. "
        "Here's what the bets actually are:</p>"
        + chaps
        + gap_note
        + '<div style="margin-top:8px">'
        + gaps_text
        + (
            f'<div style="display:flex;gap:11px;align-items:flex-start;font-size:13px;'
            f'line-height:1.5;color:#33474c;margin-bottom:9px">'
            f'<span style="flex-shrink:0;width:22px;height:22px;border-radius:6px;'
            f"background:{_AMBER};color:#fff;font-family:'IBM Plex Mono';"
            "font-weight:700;font-size:11px;display:flex;align-items:center;"
            'justify-content:center;margin-top:1px">&#10005;</span>'
            "<div><b>Don't reshuffle within your largest bet.</b> "
            "Swapping one name for another on the same axis leaves ENB flat &#8212; it's the same bet wearing a different ticker.</div>"
            "</div>"
        )
        + f'<div style="display:flex;gap:11px;align-items:flex-start;font-size:13px;'
        f'line-height:1.5;color:#33474c">'
        f'<span style="flex-shrink:0;width:22px;height:22px;border-radius:6px;'
        f"background:{_AMBER};color:#fff;font-family:'IBM Plex Mono';"
        "font-weight:700;font-size:11px;display:flex;align-items:center;"
        'justify-content:center;margin-top:1px">i</span>'
        "<div><b>This is descriptive, not advice.</b> "
        "It names the axes you lack; it does not tell you to enter any of them.</div>"
        "</div>"
        "</div>"
        "</div></details>"
    )

    # Data-driven framing: the narrative must match the actual decomposition.
    # A book is "concentrated" only when one axis dominates the variance.
    concentrated = bool(pc_variance) and pc_variance[0] >= 0.40
    main_enb = (
        '<div class="risk-enb">'
        '<div class="risk-enbnum">'
        f'<div class="risk-big-n">{enb:.1f}</div>'
        f'<div class="risk-of">of {total_h} names</div>'
        '<div class="risk-lab">Effective bets</div>'
        "</div>"
        '<div class="risk-enbright">'
        f"<p>You hold {total_h} names, but the math says they behave like "
        f"<b>~{enb:.0f} independent bets</b>. The first principal portfolio "
        f"&#8212; essentially &#8220;{_bet_name(0)}&#8221; &#8212; "
        + (
            f"carries <b>{pc_variance[0]:.0%}</b> of your variance"
            f"{' &#8212; it dominates' if concentrated else ', the largest single share'}. "
            if pc_variance
            else "variance attribution is not yet available. "
        )
        + (
            "This is the rigorous version of the concentration flag: "
            "<b>one axis dominates</b> &#8212; you own &#8220;one thing, many ways.&#8221;</p>"
            if concentrated
            else "No single axis dominates &#8212; your risk is <b>genuinely spread</b> "
            "across many independent bets, not one. The concentration flag is about "
            "the systematic-share dial above, not this.</p>"
        )
        + pc_rows
        + "</div></div>"
    )

    return (
        f'<div class="ri-sec">How many real bets? {tooltip("Effective bets")}</div>'
        + main_enb
        + drill
    )


def _sector_section(macro: dict[str, Any]) -> str:
    """GICS sector weights + HHI + sector gaps tagged NOT A TRADE CALL."""
    sector_weights: dict[str, float] = macro.get("sector_weights") or {}
    sector_hhi = macro.get("sector_hhi")
    sector_gaps: list[str] = macro.get("sector_gaps") or []

    if not sector_weights:
        return (
            f'<div class="ri-sec">{tooltip("GICS sector", "Sector concentration")}</div>'
            f'<div class="barwrap" style="background:{_CARD};border:1px solid {_LINE};'
            f'border-radius:14px;padding:18px 20px">'
            f'<p style="font-size:12px;color:{_MUT}">DATA-GAP: sector weights not available &#8212; '
            "run weekly-brief to populate.</p>"
            "</div>"
        )

    max_w = max(sector_weights.values()) if sector_weights else 1.0
    rows = ""
    for sector, w in sorted(sector_weights.items(), key=lambda kv: kv[1], reverse=True):
        bar_pct = w / max_w * 100.0
        rows += (
            f'<div class="risk-wrow">'
            f'<span class="risk-wn">{_html.escape(sector)}</span>'
            f'<span class="risk-wt"><span class="risk-wf" style="width:{bar_pct:.0f}%"></span></span>'
            f'<span class="risk-wv">{w:.0%}</span>'
            "</div>"
        )

    hhi_note = ""
    if sector_hhi is not None:
        hhi_label = (
            "HIGH" if sector_hhi > 0.25 else "MODERATE" if sector_hhi > 0.15 else "LOW"
        )
        hhi_note = (
            f"<div style=\"font-family:'IBM Plex Mono',monospace;font-size:10.5px;"
            f"color:{_FAINT};margin-top:8px;border-top:1px dashed {_LINE};"
            'padding-top:9px;display:flex;align-items:center">'
            f'{tooltip("HHI", "Concentration (HHI)")}&nbsp;= {sector_hhi:.2f} &middot; {hhi_label}'
            "</div>"
        )

    gap_note = ""
    if sector_gaps:
        gaps_str = ", ".join(f"<b>0% {_html.escape(g)}</b>" for g in sector_gaps)
        gap_note = (
            f'<div style="margin-top:12px;background:#f7fafb;border:1px solid {_LINE};'
            f"border-left:4px solid {_G1};border-radius:10px;padding:11px 13px;"
            f'font-size:12px;color:#33474c;line-height:1.55">'
            "<b>Diversification gaps (descriptive):</b> the book holds "
            + gaps_str
            + ". Historically these sectors have moved less in step with a tech-and-growth bet "
            "than the sectors already held. "
            "<span style=\"font-family:'IBM Plex Mono',monospace;font-size:9px;font-weight:600;"
            "background:#eef1f4;color:var(--risk-mut);padding:1px 6px;border-radius:5px;"
            'letter-spacing:.05em;margin-left:4px">DESCRIPTIVE &middot; NOT A TRADE CALL</span>'
            '<br><span style="font-size:11px;color:var(--risk-mut)">'
            "This names where you have no exposure &#8212; it does not recommend entering any sector."
            "</span>"
            "</div>"
        )

    top3_pct = sum(sorted(sector_weights.values(), reverse=True)[:3])

    return (
        f'<div class="ri-sec">{tooltip("GICS sector", "Sector concentration")}</div>'
        f'<div class="barwrap" style="background:{_CARD};border:1px solid {_LINE};'
        'border-radius:14px;padding:18px 20px">'
        f'<p class="bcap2" style="font-size:12px;color:{_MUT};line-height:1.55;margin:0 0 12px">'
        f"Where the book clusters by industry (GICS). "
        f"<b>Top-3 sectors = {top3_pct:.0%}</b> of the book &#8212; the concentration flag "
        "isn&#8217;t just &#8220;the market,&#8221; it&#8217;s the sector tilt.</p>"
        + rows
        + hhi_note
        + gap_note
        + "</div>"
    )


def _who_owns(macro: dict[str, Any]) -> str:
    """Marginal risk contribution vs dollar weight — RISK &#8800; $ contrast."""
    risk_contribution: dict[str, float] = macro.get("risk_contribution") or {}
    holdings_meta: list[dict[str, Any]] = macro.get("holdings_meta") or []
    coverage_h = macro.get("coverage_holdings", "?")
    total_h = macro.get("total_holdings", "?")

    if not risk_contribution:
        return (
            f'<div class="ri-sec">Who owns the bet <span style="font-family:\'IBM Plex Mono\',monospace;'
            f"font-size:8px;font-weight:700;letter-spacing:.08em;background:{_PETROL};color:#fff;"
            'padding:1px 6px;border-radius:6px;margin-left:8px;vertical-align:middle">RISK &#8800; $</span></div>'
            f'<div class="barwrap" style="background:{_CARD};border:1px solid {_LINE};'
            f'border-radius:14px;padding:18px 20px">'
            f'<p style="font-size:12px;color:{_MUT}">DATA-GAP: risk contribution not available &#8212; '
            "run weekly-brief to populate.</p>"
            "</div>"
        )

    # Build name→meta lookup
    meta_lookup: dict[str, dict[str, Any]] = {
        str(m.get("ticker", "")): m for m in holdings_meta
    }

    # Sort by risk contribution descending
    sorted_rc = sorted(risk_contribution.items(), key=lambda kv: kv[1], reverse=True)
    max_rc = sorted_rc[0][1] if sorted_rc else 1.0

    rows = ""
    for ticker, rc in sorted_rc:
        meta = meta_lookup.get(ticker, {})
        name = str(meta.get("name", ticker))
        weight = meta.get("weight")
        bar_pct = rc / max_rc * 100.0

        weight_str = f"~{float(weight):.0%} of $" if weight is not None else ""

        rows += (
            f'<div class="risk-wrow">'
            f'<span class="risk-wn">{_html.escape(ticker)} '
            f"<span style=\"color:{_FAINT};font-family:'IBM Plex Sans',sans-serif;font-size:9.5px\">{_html.escape(name)}</span>"
            "</span>"
            f'<span class="risk-wt"><span class="risk-wf" style="width:{bar_pct:.0f}%"></span></span>'
            f'<span class="risk-wv">{rc:.0%} of risk'
            + (
                f'<br><span style="font-size:9px;color:{_FAINT}">{weight_str}</span>'
                if weight_str
                else ""
            )
            + "</span>"
            "</div>"
        )

    # Find a good contrast example for the caption
    caption_example = ""
    for ticker, rc in sorted_rc[:1]:
        meta = meta_lookup.get(ticker, {})
        weight = meta.get("weight")
        if weight is not None:
            caption_example = (
                f"{ticker} is <b>{rc:.0%} of risk on ~{float(weight):.0%} of dollars</b> "
                "(higher volatility), so it punches above its size. "
            )

    uncovered = (
        int(total_h) - int(coverage_h)
        if isinstance(total_h, int) and isinstance(coverage_h, int)
        else "?"
    )

    gap_note = (
        f"<div style=\"font-family:'IBM Plex Mono',monospace;font-size:10.5px;"
        f"color:{_FAINT};margin-top:8px;border-top:1px dashed {_LINE};"
        'padding-top:9px;display:flex;align-items:center">'
        f"TOP {min(5, len(sorted_rc))} = ~{sum(rc for _,rc in sorted_rc[:5]):.0%} OF SYSTEMATIC RISK "
        f"&middot; {uncovered} HOLDINGS UNCOVERED "
        f"<span style=\"font-family:'IBM Plex Mono',monospace;font-size:9px;font-weight:600;"
        "background:#eef1f4;color:var(--risk-mut);padding:1px 6px;border-radius:5px;"
        'letter-spacing:.05em;margin-left:8px">DATA-GAP</span>'
        "</div>"
    )

    return (
        f'<div class="ri-sec">Who owns the bet '
        f"<span style=\"font-family:'IBM Plex Mono',monospace;font-size:8px;font-weight:700;"
        f"letter-spacing:.08em;background:{_PETROL};color:#fff;"
        'padding:1px 6px;border-radius:6px;margin-left:8px;vertical-align:middle">RISK &#8800; $</span>'
        f"</div>"
        f'<div class="barwrap" style="background:{_CARD};border:1px solid {_LINE};'
        'border-radius:14px;padding:18px 20px">'
        f'<p class="bcap2" style="font-size:12px;color:{_MUT};line-height:1.55;margin:0 0 12px">'
        "Each holding's share of <b>portfolio risk</b> (variance), summing to 100% &#8212; "
        "<b>not dollar weight</b>. "
        + caption_example
        + "Trimming the biggest risk owners clears the flag fastest.</p>"
        + rows
        + gap_note
        + "</div>"
    )


def _drift(macro: dict[str, Any]) -> str:
    """8-week sys_share history sparkline. Falls back to 'building history' if < 3 pts."""
    history: list[Any] = macro.get("sys_share_history") or []
    if len(history) < 3:
        return (
            '<div class="ri-sec"><span style="color:var(--risk-amber)">Flagged &middot;</span> '
            "Has it moved?</div>"
            f'<div class="risk-drift">'
            f'<div style="flex:1">'
            f'<div class="risk-dk">'
            f'{tooltip("Drift", "Systematic share &middot; drift")} &middot; last 8 weeks</div>'
            f'<div class="risk-dt" style="margin-top:6px">'
            "building history &#8212; fewer than 3 weeks of data available. "
            "Check back next week."
            "</div></div>"
            "</div>"
        )

    # Build a simple SVG sparkline
    values = [float(pt[1]) for pt in history[-8:]]
    dates = [str(pt[0]) for pt in history[-8:]]
    n = len(values)
    min_v = min(values)
    max_v = max(values)
    v_range = max_v - min_v if max_v > min_v else 0.01

    def _y(v: float) -> float:
        return 50.0 - (v - min_v) / v_range * 40.0  # 50 px height, 5px margin

    points = " ".join(f"{i*160/(n-1):.1f},{_y(v):.1f}" for i, v in enumerate(values))
    flag_y = _y(0.60)
    last_val = values[-1]
    first_val = values[0]
    trend_color = _AMBER if last_val > 0.60 else _G1

    spark_svg = (
        f'<svg class="spark" viewBox="0 0 160 56" preserveAspectRatio="none" '
        f'style="width:160px;height:56px;flex-shrink:0">'
        f'<line x1="0" y1="{flag_y:.1f}" x2="160" y2="{flag_y:.1f}" '
        f'stroke="{_AMBER}" stroke-dasharray="3 3" stroke-width="1" opacity=".55"/>'
        f'<polyline points="{points}" fill="none" stroke="{trend_color}" stroke-width="2.4"/>'
        f'<circle cx="160" cy="{_y(last_val):.1f}" r="3.6" fill="{trend_color}"/>'
        f'<text x="2" y="52" font-family="IBM Plex Mono" font-size="7" fill="{_FAINT}">'
        f"{_html.escape(dates[0])} {first_val:.0%}</text>"
        f'<text x="90" y="52" font-family="IBM Plex Mono" font-size="7" fill="{trend_color}">'
        f"now {last_val:.0%}</text>"
        "</svg>"
    )

    trend_dir = "climbing" if last_val > first_val else "falling"
    trend_text = (
        (
            f"The market bet is <b>{trend_dir}</b>: "
            f'<span class="risk-up">{first_val:.0%} &#8594; {last_val:.0%}</span> '
            f"over {n} weeks" + (", crossing the 60% line." if last_val > 0.60 else ".")
        )
        + " <b>Re-read the latest weekly brief</b> and confirm the tilt is intentional."
    )

    return (
        '<div class="ri-sec"><span style="color:var(--risk-amber)">Flagged &middot;</span> '
        "Has it moved?</div>"
        f'<div class="risk-drift">'
        '<div style="flex:1">'
        f'<div class="risk-dk">'
        f'Systematic share &middot; last 8 weeks {tooltip("Drift")}</div>'
        f'<div class="risk-dt" style="margin-top:6px">{trend_text}</div>'
        "</div>" + spark_svg + "</div>"
    )


def _teach() -> str:
    return (
        '<div class="ri-sec" id="teach">'
        f'<span style="color:{_PETROL}">Teach me</span> &middot; The risk story</div>'
        '<details class="teach" open>'
        '<summary style="list-style:none;cursor:pointer;padding:14px 17px;'
        f"font-family:'IBM Plex Mono',monospace;font-size:11px;letter-spacing:.1em;"
        f"text-transform:uppercase;color:{_PETROL};font-weight:600;"
        'display:flex;justify-content:space-between;align-items:center">'
        f"<span style=\"font-family:'Fraunces',serif;font-weight:700;font-size:15px;"
        f'text-transform:none;color:{_INK}">Plain-English walkthrough</span>'
        "<span>&#8722;</span></summary>"
        '<div style="padding:4px 17px 14px">'
        # Q1
        f'<div style="padding:14px 0;border-bottom:1px solid #eef3f4">'
        f"<div style=\"font-family:'IBM Plex Mono',monospace;font-size:10px;"
        f'font-weight:600;color:{_PETROL};letter-spacing:.1em">QUESTION 1</div>'
        f"<div style=\"font-family:'Fraunces',serif;font-weight:700;font-size:16px;"
        'margin:3px 0 4px">How much market am I holding?</div>'
        f'<p style="font-size:12px;color:{_MUT};line-height:1.5;margin:0 0 9px">'
        '"Net beta" = how hard the book swings vs the market. 1.0 = step-for-step.</p>'
        f'<p style="font-size:12.5px;line-height:1.55;color:#33474c;margin-top:8px">'
        "<b>The net beta tells you the swing size.</b> No defined line for size &#8212; so it's grey.</p>"
        "</div>"
        # Q2
        f'<div style="padding:14px 0;border-bottom:1px solid #eef3f4">'
        f"<div style=\"font-family:'IBM Plex Mono',monospace;font-size:10px;"
        f'font-weight:600;color:{_PETROL};letter-spacing:.1em">QUESTION 2</div>'
        f"<div style=\"font-family:'Fraunces',serif;font-weight:700;font-size:16px;"
        'margin:3px 0 4px">Is it spread out, or one big bet?</div>'
        f'<p style="font-size:12px;color:{_MUT};line-height:1.5;margin:0 0 9px">'
        "Systematic share: the fraction of variance in market-wide forces vs individual names.</p>"
        f'<p style="font-size:12.5px;line-height:1.55;color:#33474c;margin-top:8px">'
        "<b>The systematic-share strip shows you exactly where you sit.</b> "
        "Past 60% = the amber line trips.</p>"
        "</div>"
        # Q3
        f'<div style="padding:14px 0;border-bottom:1px solid #eef3f4">'
        f"<div style=\"font-family:'IBM Plex Mono',monospace;font-size:10px;"
        f'font-weight:600;color:{_PETROL};letter-spacing:.1em">QUESTION 3</div>'
        f"<div style=\"font-family:'Fraunces',serif;font-weight:700;font-size:16px;"
        "margin:3px 0 4px\">What's driving it?</div>"
        f'<p style="font-size:12px;color:{_MUT};line-height:1.5;margin:0 0 9px">'
        "See the factor + sector breakdowns above.</p>"
        f'<p style="font-size:12.5px;line-height:1.55;color:#33474c;margin-top:8px">'
        "<b>Long market, growth &amp; momentum; sector-heavy.</b> The dominant factor dwarfs the rest &#8212; "
        "that's why concentration is flagged.</p>"
        "</div>"
        # Q4
        f'<div style="padding:14px 0">'
        f"<div style=\"font-family:'IBM Plex Mono',monospace;font-size:10px;"
        f'font-weight:600;color:{_PETROL};letter-spacing:.1em">QUESTION 4</div>'
        f"<div style=\"font-family:'Fraunces',serif;font-weight:700;font-size:16px;"
        'margin:3px 0 4px">So what should I watch?</div>'
        f'<p style="font-size:12px;color:{_MUT};line-height:1.5;margin:0 0 9px">'
        "Descriptive dials &#8212; check whether any defined lines tripped this week.</p>"
        f'<p style="font-size:12.5px;line-height:1.55;color:#33474c;margin-top:8px">'
        "Confirm the <b>concentration</b> and any <b>upward drift</b> are intentional. "
        "Nothing here says to enter or exit positions.</p>"
        "</div>"
        "</div></details>"
    )


def _flags_footer(
    flags: list[str],
    coverage_holdings: Any,
    total_holdings: Any,
) -> str:
    flag_cards = ""
    for flag in flags:
        meaning, action = _FLAG_MEANING.get(
            flag,
            ("Unrecognized flag.", "See the weekly brief markdown for detail."),
        )
        flag_cards += (
            '<div class="risk-flagcard">'
            '<span class="risk-fdot"></span>'
            '<div class="risk-ft">'
            f"<b>{flag}</b>"
            f"{meaning} {action}"
            "</div></div>"
        )

    n_flags = len(flags)
    sec_label = (
        f'<span style="color:{_AMBER}">{n_flags} active flag{"s" if n_flags != 1 else ""}</span>'
        if n_flags > 0
        else "No active flags"
    )

    return (
        f'<div class="ri-sec">{sec_label}</div>'
        + flag_cards
        + f'<div class="foot" style="margin-top:24px;font-size:12px;color:{_MUT};'
        f"background:#fff;border:1px dashed {_LINE};border-radius:10px;"
        'padding:11px 14px;display:flex;align-items:center;gap:9px;line-height:1.5">'
        f'<span style="width:7px;height:7px;border-radius:50%;background:{_AMBER};flex-shrink:0"></span>'
        f'<div><b style="color:{_INK}">Colour = within-line / neutral / look-here, never &#8220;good/bad risk&#8221;.</b> '
        "These dials surface character to read &#8212; heuristics, not validated edges. "
        "Google AI is an attributed second opinion, not the verdict. "
        "Nothing here forecasts returns or tells you to enter or exit positions.</div>"
        "</div>"
        f'<div class="risk-cov">COVERAGE: {coverage_holdings} / {total_holdings} holdings '
        f"&middot; source: weekly-brief macro scrubber</div>"
    )


# ===========================================================================
# Pure composer — NO Streamlit, fully testable
# ===========================================================================


def _compose(macro: dict[str, Any] | None, ai_html: str = "") -> str:
    """Compose the full Risk-tab HTML.

    Args:
        macro:    the macro dict from load_brief_summary(), or None.
        ai_html:  optional pre-rendered HTML for the Google-AI second-opinion
                  panel.  When non-empty it is injected between the drift
                  section and the teach section (matching mockup order).
                  Ignored (not inserted) when empty / falsy — _compose stays
                  fully testable without a live CaseResult.

    Returns:
        Complete HTML string (safe to pass to st.markdown(unsafe_allow_html=True)).
        Never raises — degrades gracefully to safe-fallback when macro is None.
    """
    if macro is None:
        return (
            '<div class="ri-h1">Portfolio Risk</div>'
            f'<p style="color:{_MUT}">No macro-beta data. '
            "Run <code>python -m application.cli weekly-brief</code> "
            "(the scrubber runs inside it).</p>"
        )

    flags: list[str] = list(macro.get("flags") or [])

    parts = [
        _header(),
        _status_banner(flags),
        _contract_legend(),
        _vitals(macro),
        _lens_nav(),
        _standing(macro),
        _dials(macro),
        _grill_drill(flags),
        _evidence_bands(macro),
        _factor_chart(macro),
        _enb_section(macro),
        _sector_section(macro),
        _who_owns(macro),
        _drift(macro),
    ]
    # Mockup order: _drift → [Second opinion · Google AI] → _teach → _flags_footer
    if ai_html:
        parts.append(ai_html)
    parts += [
        _teach(),
        _flags_footer(
            flags,
            macro.get("coverage_holdings", "?"),
            macro.get("total_holdings", "?"),
        ),
    ]
    return "\n".join(parts)


# ===========================================================================
# Streamlit entrypoint
# ===========================================================================


def render(path: str = "data/personal/brief_summary.json") -> None:
    """Streamlit entrypoint: load macro → render v8 status-first layout."""
    summary = load_brief_summary(path)
    macro = (summary or {}).get("macro") if summary else None

    # Build AI second-opinion panel HTML BEFORE composing (spec §9 — no live
    # Gemini at render time; cache-first load only).  ai_html is "" when
    # off-local or cache empty — _compose ignores empty strings.
    ai_html = ""
    if macro is not None:
        from application.risk_second_opinion import load_cached_risk_second_opinion

        ai_html = render_risk_second_opinion(load_cached_risk_second_opinion())

    # Single st.markdown call — ensures mockup order:
    #   _drift → Second opinion · Google AI → _teach → _flags_footer
    st.markdown(_compose(macro, ai_html), unsafe_allow_html=True)
