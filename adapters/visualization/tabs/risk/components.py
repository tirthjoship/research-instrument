"""Header, banner, nav, vitals, dials."""

from __future__ import annotations

from typing import Any

from adapters.visualization.components.tooltip import tooltip

from ._theme import *  # noqa: F403, F405


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
            + _metric_evidence("enb")
            + "</div>"
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
            f'<div class="risk-vk">Net beta (SPY){tooltip("Net beta", "ⓘ")}</div>'
            f'<div class="risk-vv">{spy_beta:.2f}<small>&times;</small></div>'
            f'<div class="risk-vs">{ci_text}&nbsp;&middot; grey = no line</div>'
            + _metric_evidence("net_beta")
            + "</div>"
        )

    # Downside beta
    if downside_beta is not None:
        cards.append(
            f'<div class="risk-vit grey">'
            f'<div class="risk-vk">{tooltip("Downside beta")}</div>'
            f'<div class="risk-vv">{float(downside_beta):.2f}<small>&times;</small></div>'
            f'<div class="risk-vs">falls harder than it rises</div>'
            + _metric_evidence("downside_beta")
            + "</div>"
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
        + _metric_evidence("systematic_share")
        + "</div>"
    )

    # Diversification ratio
    if div_ratio is not None:
        cards.append(
            f'<div class="risk-vit grey">'
            f'<div class="risk-vk">{tooltip("Diversification ratio")}</div>'
            f'<div class="risk-vv">{float(div_ratio):.1f}<small>&times;</small></div>'
            f'<div class="risk-vs">low = names co-move</div>'
            + _metric_evidence("diversification_ratio")
            + "</div>"
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
