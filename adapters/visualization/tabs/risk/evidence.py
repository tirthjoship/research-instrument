"""Evidence bands, grill drill, flags footer."""

from __future__ import annotations

from typing import Any

from adapters.visualization.components.tooltip import tooltip
from domain.risk_rubric import classify_net_beta

from ._theme import *  # noqa: F403, F405


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
        f'<span>NET MARKET BETA (SPY){tooltip("Net beta", "ⓘ")}</span>'
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
