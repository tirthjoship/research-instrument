"""Fama-French factor chart section."""

from __future__ import annotations

import html as _html
from typing import Any

from adapters.visualization.components.tooltip import tooltip

from ._theme import *  # noqa: F403, F405


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

    # Sort factor rows by descending |net_beta| so highest-impact factors rise to the top.
    # Display order only — does not affect which factors are shown or badge/READ logic.
    sorted_factors = sorted(betas.items(), key=lambda kv: abs(kv[1]), reverse=True)

    rows = ""
    for factor, beta_val in sorted_factors:
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

        # Hover-cloud tooltip for this factor (graceful: no tooltip if term absent)
        _glossary_term = _FACTOR_GLOSSARY_TERMS.get(factor)
        factor_ttip_html = tooltip(_glossary_term, "ⓘ") if _glossary_term else ""

        row_class = "frow supp" if is_suppressed else "frow"
        name_color = _FAINT if is_suppressed else _INK
        val_color = _FAINT if is_suppressed else _INK

        rows += (
            f'<div class="{row_class}" style="display:grid;grid-template-columns:128px 1fr 50px;'
            'gap:10px;align-items:center;font-size:11.5px;margin-bottom:9px">'
            f"<span style=\"font-family:'IBM Plex Mono',monospace;color:{name_color};"
            'display:flex;align-items:center;gap:6px;flex-wrap:wrap">'
            f"{_html.escape(factor)}{subtitle_html}{factor_ttip_html}&nbsp;{dom_label}</span>"
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

    # --- "Beyond the market" tilts line ---
    # Non-SPY, non-suppressed factors with their direction and human label.
    tilt_factors = [
        (f, v) for f, v in betas.items() if f != "SPY" and f not in suppressed
    ]
    if tilt_factors:
        tilt_parts: list[str] = []
        for tf, tv in tilt_factors:
            direction = "long" if tv >= 0.0 else "short"
            human = _FACTOR_DISPLAY_NAMES.get(tf, tf)
            tilt_parts.append(f"{direction} {human}")
        tilt_list = (
            " and ".join(tilt_parts)
            if len(tilt_parts) <= 2
            else (", ".join(tilt_parts[:-1]) + ", and " + tilt_parts[-1])
        )
        tilts_text = (
            "Beyond the market (SPY): the distinctive style tilts are "
            + tilt_list
            + " &#8212; the other style factors sit near zero."
        )
    else:
        tilts_text = (
            "Beyond the market, no style factor stands out &#8212; "
            "the book is essentially a broad-market bet."
        )

    tilts_html = f'<br><span style="color:{_FAINT}">' + tilts_text + "</span>"

    # --- Combined .fnote block: READ + tilts line + whisker footnote ---
    fnote_html = (
        f"<div style=\"font-family:'IBM Plex Mono',monospace;font-size:10px;color:{_FAINT};"
        'margin-top:12px;border-top:1px dashed var(--risk-line);padding-top:9px;line-height:1.6">'
        + read_html
        + tilts_html
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
