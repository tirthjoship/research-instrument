"""Risk tab — Unit A macro-beta scrubber, promoted from CLI markdown."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

import plotly.graph_objects as go
import streamlit as st

from adapters.visualization.components.charts import apply_dossier_template
from adapters.visualization.components.metrics import render_verdict_card
from adapters.visualization.components.tooltip import tooltip
from adapters.visualization.data_loader import load_brief_summary
from domain.risk_rubric import (
    NetBetaBand,
    ShareBand,
    classify_net_beta,
    classify_systematic_share,
    net_beta_position,
)

# Mono distance-ramp colours: neutral gray at market-like centre; deeper slate as
# the book drifts further from market-like.  NOT red/green — risk is character,
# not quality.  A band is descriptive; none is "good" or "bad" by itself.
_NET_BETA_BAND_COLOURS: dict[NetBetaBand, str] = {
    NetBetaBand.HEDGED: "#475569",  # deep slate — far from market
    NetBetaBand.DEFENSIVE: "#94A3B8",  # mid slate
    NetBetaBand.MARKET_LIKE: "#CBD5E1",  # lightest — at-market anchor
    NetBetaBand.ELEVATED: "#94A3B8",  # mid slate — drifting above 1
    NetBetaBand.AGGRESSIVE: "#475569",  # deep slate — far above market
}

_SHARE_BAND_COLOURS: dict[ShareBand, str] = {
    ShareBand.STOCK_SPECIFIC: "#CBD5E1",  # lightest — idiosyncratic-dominant
    ShareBand.BALANCED: "#94A3B8",
    ShareBand.MACRO_LEANING: "#64748B",
    ShareBand.MACRO_DOMINATED: "#334155",  # deepest — fully macro-driven
}

# Widths (%) for each band segment in the strip, order L→R
_NET_BETA_WIDTHS: list[tuple[NetBetaBand, float]] = [
    (NetBetaBand.HEDGED, 20.0),  # −0.5 → 0  (20% of −0.5..2.0 domain)
    (NetBetaBand.DEFENSIVE, 32.0),  # 0 → 0.8
    (NetBetaBand.MARKET_LIKE, 16.0),  # 0.8 → 1.2
    (NetBetaBand.ELEVATED, 16.0),  # 1.2 → 1.6
    (NetBetaBand.AGGRESSIVE, 16.0),  # 1.6 → 2.0 (+clamp remainder)
]

_SHARE_WIDTHS: list[tuple[ShareBand, float]] = [
    (ShareBand.STOCK_SPECIFIC, 40.0),  # 0 → 0.40
    (ShareBand.BALANCED, 20.0),  # 0.40 → 0.60
    (ShareBand.MACRO_LEANING, 15.0),  # 0.60 → 0.75
    (ShareBand.MACRO_DOMINATED, 25.0),  # 0.75 → 1.00
]


def _band_strip_html(
    *,
    label: str,
    band_widths: Sequence[tuple[Any, float]],
    band_colours: Mapping[Any, str],
    needle_pct: float,
    pill_text: str,
    value_text: str,
    anchor_left: str = "",
    anchor_right: str = "",
    flag_pct: float | None = None,
) -> str:
    """Render a horizontal band strip with a needle/marker as HTML.

    Args:
        label: Strip section label (e.g. "NET BETA").
        band_widths: Ordered list of (band_enum, width_pct) pairs.
        band_colours: Mapping from band_enum → hex colour.
        needle_pct: Position 0..100 of the needle on the strip.
        pill_text: The band label (e.g. "Elevated").
        value_text: Full display string (e.g. "1.42 — Elevated").
        anchor_left: Label under the left edge of the strip.
        anchor_right: Label under the right edge of the strip.
        flag_pct: If provided, renders a flag tick on the strip at this position.
    """
    # Build band segments
    segments_html = ""
    for band, width in band_widths:
        colour = band_colours.get(band, "#CBD5E1")
        segments_html += (
            f'<div style="width:{width}%;background:{colour};height:100%;'
            f'display:inline-block;"></div>'
        )

    # Needle
    needle_html = (
        f'<div style="position:absolute;left:{needle_pct:.1f}%;top:0;bottom:0;'
        f'width:3px;background:#14181F;border-radius:2px;transform:translateX(-50%);">'
        f"</div>"
        f'<div style="position:absolute;left:{needle_pct:.1f}%;bottom:-7px;'
        f"width:0;height:0;border-left:5px solid transparent;"
        f"border-right:5px solid transparent;border-top:7px solid #14181F;"
        f'transform:translateX(-50%);"></div>'
    )

    # Optional flag tick (e.g. systematic-share threshold at 60%)
    flag_html = ""
    if flag_pct is not None:
        flag_html = (
            f'<div style="position:absolute;left:{flag_pct:.1f}%;top:-4px;bottom:-4px;'
            f'width:2px;background:#C9810E;opacity:0.8;transform:translateX(-50%);">'
            f'<span style="position:absolute;top:-14px;left:50%;transform:translateX(-50%);'
            f"font-family:'IBM Plex Mono',monospace;font-size:9px;color:#C9810E;"
            f'white-space:nowrap;">threshold</span>'
            f"</div>"
        )

    # Anchor labels
    anchor_html = (
        f'<div style="display:flex;justify-content:space-between;'
        f"font-family:'IBM Plex Mono',monospace;font-size:10px;"
        f'color:#717885;margin-top:4px;">'
        f"<span>{anchor_left}</span><span>{anchor_right}</span></div>"
    )

    # Pill
    pill_html = (
        f'<span style="display:inline-block;padding:2px 10px;border-radius:999px;'
        f"background:#E3E7EC;color:#3A4250;font-family:'IBM Plex Mono',monospace;"
        f"font-size:11px;font-weight:600;letter-spacing:.08em;text-transform:uppercase;"
        f'margin-right:8px;">{pill_text}</span>'
    )

    return (
        f'<div style="margin-bottom:1.8rem;">'
        f"<div style=\"font-family:'IBM Plex Mono',monospace;font-size:.72rem;"
        f'letter-spacing:.2em;text-transform:uppercase;color:#717885;margin-bottom:8px;">'
        f"{label}</div>"
        f"<div style=\"font-family:'IBM Plex Mono',monospace;font-size:.85rem;"
        f'color:#14181F;margin-bottom:10px;">'
        f"{pill_html}{value_text}</div>"
        f'<div style="position:relative;height:18px;border-radius:4px;overflow:visible;'
        f'background:transparent;width:100%;">'
        f'<div style="display:flex;height:100%;border-radius:4px;overflow:hidden;width:100%;">'
        f"{segments_html}"
        f"</div>"
        f"{needle_html}{flag_html}"
        f"</div>"
        f"{anchor_html}"
        f"</div>"
    )


def _render_band_strips(net_beta: float, sys_share: float) -> None:
    """Render the two where-do-I-stand distance-ramp band strips above the charts.

    Uses config/markets/us.yaml systematic_share_threshold=0.60 (default in rubric).
    Risk is character, not quality — bands are descriptive, not good/bad.
    """
    _SHARE_FLAG = 0.60  # matches us.yaml macro_beta.systematic_share_threshold

    beta_band = classify_net_beta(net_beta)
    share_band = classify_systematic_share(sys_share, flag=_SHARE_FLAG)
    beta_pos = net_beta_position(net_beta)
    share_pos = sys_share * 100.0  # 0..1 → 0..100

    beta_html = _band_strip_html(
        label="NET BETA — Market sensitivity character",
        band_widths=_NET_BETA_WIDTHS,
        band_colours=_NET_BETA_BAND_COLOURS,
        needle_pct=beta_pos,
        pill_text=beta_band.value,
        value_text=f"{net_beta:.2f} — {beta_band.value}",
        anchor_left="0",
        anchor_right="1.0 (market)",
    )

    share_html = _band_strip_html(
        label="SYSTEMATIC SHARE — Where the book’s variance lives",
        band_widths=_SHARE_WIDTHS,
        band_colours=_SHARE_BAND_COLOURS,
        needle_pct=share_pos,
        pill_text=share_band.value,
        value_text=f"{sys_share:.0%} — {share_band.value}",
        flag_pct=_SHARE_FLAG * 100.0,
    )

    st.markdown(
        f'<div class="ri-sec">WHERE DO I STAND</div>'
        f'<div style="background:#FFFFFF;border:1px solid #E3E7EC;border-radius:14px;'
        f"padding:1.4rem 1.6rem 1.2rem;margin-bottom:1.4rem;"
        f'box-shadow:0 1px 2px rgba(20,40,60,.05),0 8px 20px rgba(20,40,60,.05);">'
        f"<p style=\"font-family:'IBM Plex Sans',sans-serif;font-size:.8rem;"
        f'color:#717885;margin:0 0 1.2rem;line-height:1.5;">'
        f"Each strip shows the character of this book’s risk exposure. "
        f"Bands are descriptive — distance from the market-like anchor, "
        f"not a rating. Neither extreme is inherently good or bad.</p>"
        f"{beta_html}{share_html}"
        f"</div>",
        unsafe_allow_html=True,
    )


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


def render(path: str = "data/personal/brief_summary.json") -> None:
    st.markdown(
        '<h1 class="ri-h1" style="font-size:1.9rem;margin-bottom:.25rem">'
        "Portfolio Risk</h1>"
        '<p class="ri-sub" style="margin-bottom:.2rem">'
        "Macro-beta scrubber — where your book’s risk actually comes from.</p>"
        "<p style=\"font-family:'IBM Plex Mono',monospace;font-size:.68rem;"
        'letter-spacing:.1em;color:var(--ri-muted);margin-bottom:1rem">'
        "HEURISTIC SURFACING DIALS &nbsp;&middot;&nbsp; NOT VALIDATED EDGES &nbsp;&middot;&nbsp; ADR-052</p>",
        unsafe_allow_html=True,
    )

    summary = load_brief_summary(path)
    macro = (summary or {}).get("macro")
    if macro is None:
        st.warning(
            "No macro-beta data. Run `python -m application.cli weekly-brief` "
            "(the scrubber runs inside it)."
        )
        return

    betas: dict[str, float] = macro.get("net_beta_by_factor", {})
    dominant = macro.get("dominant_factor")
    sys_share = float(macro.get("systematic_share", 0.0))

    # Hero metrics row — big numbers with plain-English glossary tooltips
    spy_beta = betas.get("SPY")
    beta_str = f"{spy_beta:+.2f}" if spy_beta is not None else "n/a"
    st.markdown(
        '<div class="ri-sec">Vitals</div>'
        '<div class="ri-metric-row">'
        f'<div class="ri-metric"><div class="ri-metric-lab">'
        f"{tooltip('Net beta', 'Net market beta (SPY)')}</div>"
        f'<div class="ri-metric-num">{beta_str}</div></div>'
        f'<div class="ri-metric"><div class="ri-metric-lab">'
        f"{tooltip('Systematic share')}</div>"
        f'<div class="ri-metric-num">{sys_share:.0%}</div></div>'
        f'<div class="ri-metric"><div class="ri-metric-lab">'
        f"{tooltip('Concentrated risk', 'Dominant factor')}</div>"
        f'<div class="ri-metric-num">{dominant or "none"}</div></div>'
        "</div>",
        unsafe_allow_html=True,
    )

    # ── Band strips: where-do-I-stand distance ramp (ADDITIVE — prepended above charts)
    if spy_beta is not None:
        _render_band_strips(net_beta=spy_beta, sys_share=sys_share)

    # Factor bars and donut side-by-side
    chart_col, donut_col = st.columns(2)

    with chart_col:
        st.markdown('<div class="ri-sec">FACTOR EXPOSURE</div>', unsafe_allow_html=True)
        if betas:
            fig = go.Figure(
                go.Bar(
                    x=list(betas.keys()),
                    y=list(betas.values()),
                    marker_color=[
                        "#CE2F26" if v < 0 else "#0F6E80" for v in betas.values()
                    ],
                )
            )
            fig.add_hline(
                y=1.0,
                line_dash="dot",
                line_color="#717885",
                annotation_text="moves 1:1 with market",
                annotation_font_size=11,
            )
            apply_dossier_template(fig)
            fig.update_layout(
                title="Dollar-weighted net beta by factor",
                xaxis_title="Factor",
                yaxis_title="Net beta",
                height=320,
                showlegend=False,
            )
            st.plotly_chart(fig, use_container_width=True, height=300)
            if spy_beta is not None:
                st.caption(f"Your book moves about {spy_beta:.2f}× the market.")

    with donut_col:
        st.markdown('<div class="ri-sec">RISK SOURCES</div>', unsafe_allow_html=True)
        # Systematic vs idiosyncratic donut
        idio_share = max(0.0, 1.0 - sys_share)
        donut = go.Figure(
            go.Pie(
                labels=["Systematic (macro)", "Idiosyncratic (stock-specific)"],
                values=[sys_share, idio_share],
                hole=0.55,
                marker_colors=["#0F6E80", "#1F9254"],
            )
        )
        apply_dossier_template(donut)
        donut.update_layout(
            title="Where the book's risk comes from",
            showlegend=True,
            height=320,
        )
        st.plotly_chart(donut, use_container_width=True, height=300)

    # Plain-English conclusion band
    if dominant is not None and sys_share > 0:
        conclusion_text = (
            f"{sys_share:.0%} of your book's swings trace to one market-wide "
            f"bet ({dominant}) — adding another same-direction name will not "
            f"diversify this."
        )
    else:
        conclusion_text = (
            "DATA_GAP: systematic-share or dominant-factor missing — "
            "run `python -m application.cli weekly-brief` to populate."
        )
    st.markdown(
        f'<div class="ri-conclusion">{conclusion_text}</div>',
        unsafe_allow_html=True,
    )

    # Flag cards
    flags = macro.get("flags", [])
    if flags:
        st.markdown(
            '<div class="ri-sec" style="margin-top:1rem">Risk flags</div>',
            unsafe_allow_html=True,
        )
        for flag in flags:
            meaning, action = _FLAG_MEANING.get(
                flag,
                ("Unrecognized flag.", "See the weekly brief markdown for detail."),
            )
            render_verdict_card(
                st,
                verdict=flag,
                tone="negative",
                details=f"{meaning} — {action}",
            )

    st.markdown(
        f"<div style=\"font-family:'IBM Plex Mono',monospace;font-size:.68rem;"
        f'color:var(--ri-muted);letter-spacing:.08em;margin-top:.8rem">'
        f"COVERAGE: {macro.get('coverage_holdings', '?')} / "
        f"{macro.get('total_holdings', '?')} holdings</div>",
        unsafe_allow_html=True,
    )
