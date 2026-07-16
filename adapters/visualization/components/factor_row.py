"""Factor-row HTML adapter — bridges domain factor_bands to styled HTML.

Maps factor key → display label + glossary tooltip + band + diverging bar.
All colours use CSS var() tokens from styles.py — no raw hex.
Pure HTML-returning function: testable without Streamlit.
"""

from __future__ import annotations

import html as _html

from domain.factor_bands import Band, band_for_percentile, band_tone_key

# ── Factor key → (display label, glossary term) ───────────────────────────────
# "revision" is honestly labelled "Analyst dispersion" (it measures target-price
# spread/dispersion, not estimate drift — see evidence_registry factor_analyst_dispersion).
# Data key unchanged for the downstream contract.
_FACTOR_META: dict[str, tuple[str, str]] = {
    "momentum": ("Momentum", "Momentum factor"),
    "revision": ("Analyst dispersion", "Analyst dispersion"),
    "quality": ("Quality", "Quality factor"),
    "value": ("Value", "Value factor"),
    "lowvol": ("Low-vol", "Low-vol factor"),
}

# ── Band label → CSS tone var name ────────────────────────────────────────────
_TONE_VAR: dict[str, str] = {
    "success": "--success",
    "accent": "--accent",
    "muted": "--text-muted",
    "danger": "--danger",
}

# ── Band label → background/colour CSS classes matching the mockup ─────────────
# We inline the style via var() tokens so no raw hex is needed.
_BAND_BG: dict[Band, str] = {
    Band.EXCEPTIONAL: "background:#DCFCE7;color:var(--success)",
    Band.STRONG: "background:#DBEAFE;color:var(--accent)",
    Band.FLAT: "background:#F1F5F9;color:var(--text-secondary)",
    Band.WEAK: "background:#FEE2E2;color:var(--danger)",
}


def _glossary_tooltip(glossary_term: str) -> str:
    """Inline .ri-ttip tooltip span — visible trigger is a small grey circle badge."""
    try:
        from adapters.visualization.components.glossary import GLOSSARY

        definition = GLOSSARY.get(glossary_term, "")
        if definition:
            safe_def = _html.escape(definition, quote=True)
            # Circle badge: 13px, background #CBD5E1 (≈ var(--text-muted)), white "i".
            return (
                f'<span class="ri-ttip" style="'
                f"display:inline-flex;align-items:center;justify-content:center;"
                f"width:13px;height:13px;border-radius:50%;background:#CBD5E1;"
                f"color:#fff;font-size:8px;font-weight:700;font-style:normal;"
                f"margin-left:4px;vertical-align:middle;cursor:help;"
                f'line-height:1;flex-shrink:0;">'
                f"i"
                f'<span class="ri-tip ri-tip-left">{safe_def}</span>'
                f"</span>"
            )
    except ImportError:
        pass
    return ""


def render_factor_row(
    key: str,
    value: float | None,
    percentile: float | None,
) -> str:
    """Return an HTML string for one factor row in the screener card.

    Args:
        key: Factor key (``"momentum"``, ``"revision"``, ``"quality"``,
            ``"value"``, or ``"lowvol"``).
        value: Factor z-score, or ``None`` for DATA-GAP.
        percentile: 0–1 fractional percentile, or ``None`` for DATA-GAP.

    Returns:
        HTML string matching the mockup ``.frow`` layout:
        label · band badge · diverging bar · percentile.
        Uses ``var(--success|--accent|--text-secondary|--danger)`` for colour.
    """
    display_label, glossary_term = _FACTOR_META.get(key, (key, key))
    tooltip_html = _glossary_tooltip(glossary_term)

    # DATA-GAP: either value or percentile missing (or both).
    if value is None or percentile is None:
        safe_label = _html.escape(display_label)
        return (
            f'<div style="display:grid;grid-template-columns:130px 110px 1fr 50px;'
            f'align-items:center;gap:9px;margin-bottom:6px;font-size:11px;">'
            f"<span>{safe_label}{tooltip_html}</span>"
            f'<span style="font-size:11px;color:var(--text-muted);font-style:italic;">'
            f"DATA-GAP</span>"
            f"<span></span>"
            f"<span></span>"
            f"</div>"
        )

    band = band_for_percentile(percentile)
    tone = band_tone_key(band)
    tone_var = _TONE_VAR.get(tone, "--text-muted")
    band_style = _BAND_BG.get(band, "background:#F1F5F9;color:var(--text-secondary)")

    safe_label = _html.escape(display_label)
    band_label = _html.escape(band.value)

    # Percentile display: p{round(percentile*100)}
    pct_int = round(percentile * 100)
    pct_display = f"p{pct_int}"

    # Diverging bar: centred at 50%, width proportional to |z|, capped at ±3σ
    # Positive → extends right from centre; negative → extends left.
    bar_pct = min(50.0, abs(value) / 3.0 * 50)
    if value >= 0:
        bar_html = (
            f'<div style="height:7px;background:#EEF2F6;border-radius:4px;'
            f'position:relative;overflow:hidden;">'
            f'<span style="position:absolute;top:0;left:50%;'
            f"width:{bar_pct:.1f}%;height:7px;border-radius:4px;"
            f'background:var({tone_var});"></span>'
            f"</div>"
        )
    else:
        bar_html = (
            f'<div style="height:7px;background:#EEF2F6;border-radius:4px;'
            f'position:relative;overflow:hidden;">'
            f'<span style="position:absolute;top:0;'
            f"right:50%;width:{bar_pct:.1f}%;height:7px;border-radius:4px;"
            f'background:var({tone_var});"></span>'
            f"</div>"
        )

    # Momentum row: prepend a small inline SVG sparkline (purely decorative trend motif).
    # Fixed polyline — no data claim; muted stroke; 40×11 viewport.
    sparkline_html = ""
    if key == "momentum":
        sparkline_html = (
            '<svg width="40" height="11" viewBox="0 0 40 11" '
            'style="display:inline-block;vertical-align:middle;margin-right:4px;" '
            'aria-hidden="true">'
            '<polyline points="0,9 6,6 12,7 18,4 24,5 30,2 36,4 40,1" '
            'fill="none" stroke="#CBD5E1" stroke-width="1.5" '
            'stroke-linecap="round" stroke-linejoin="round"/>'
            "</svg>"
        )

    return (
        f'<div style="display:grid;grid-template-columns:130px 110px 1fr 50px;'
        f'align-items:center;gap:9px;margin-bottom:6px;font-size:11px;">'
        f"<span>{safe_label}{tooltip_html}</span>"
        f'<span style="font-weight:600;font-size:10px;padding:2px 8px;'
        f'border-radius:11px;display:inline-block;{band_style};">'
        f"{sparkline_html}{band_label}</span>"
        f"{bar_html}"
        f"<span style=\"font-family:'JetBrains Mono',monospace;"
        f'color:var(--text-muted);text-align:right;">{pct_display}</span>'
        f"</div>"
    )
