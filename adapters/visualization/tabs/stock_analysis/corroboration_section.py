"""Corroboration evidence section — mockup-aligned renderer.

Thin: all convergence math, headline/reline copy, claim grouping, and dissent
selection live in ``corroboration_view.build_corroboration_view()``. This
module turns that view dict into HTML/Streamlit calls, plus a set of
standalone claim/readout HTML builders that are pure (no Streamlit) and
unit-tested directly.
"""

from __future__ import annotations

import html as _html
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from adapters.visualization.data_loader import CorroborationTabView

from adapters.visualization.components.info_tip import render_info
from adapters.visualization.tabs.stock_analysis.corroboration_view import (  # noqa: F401 — re-exported for backward-compat tests
    _group_claims_by_weight,
    build_corroboration_view,
)
from domain.corroboration_models import (
    ConvergenceTier,
    DirectionalView,
    HarvestedClaim,
    OurReadout,
    Stance,
)

_TILT_COLOUR: dict[str, str] = {
    "LEAN_IN": "#16A34A",
    "HOLD": "#2563EB",
    "LEAN_OUT": "#CA8A04",
    "AVOID": "#DC2626",
}

_STANCE_ICON: dict[Stance, str] = {
    Stance.BULLISH: "▲",
    Stance.BEARISH: "▼",
    Stance.NEUTRAL: "→",
}


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------


def render_corroboration_section(
    corr: "CorroborationTabView | None",
    *,
    our_readout: OurReadout | None = None,
) -> None:
    """Render the full corroboration section. Handles empty state gracefully.

    ``our_readout`` (from ``corroboration_bridge.build_readout_from_analysis``)
    takes precedence over any ``our_readout`` already carried on ``corr`` — the
    data loader always leaves that field None, so callers pass it here.
    """
    import streamlit as st

    view = build_corroboration_view(corr, our_readout=our_readout)
    st.markdown(build_corroboration_html(view), unsafe_allow_html=True)
    if view["empty"]:
        return
    # Real Streamlit expanders — not representable inside a single markdown
    # string, so these stay outside build_corroboration_html.
    _render_weak_claims(view["claims_weak"])
    _render_directional_views(view["directional_views"])


def build_corroboration_html(view: dict) -> str:  # type: ignore[type-arg]
    """Pure assembler: header → headline/reline → two-col → strong/moderate
    claim cards → CONFLICTED box → dissent callout, as one HTML string.

    Everything except the weak-signals and directional-tilt expanders (real
    Streamlit widgets — see render_corroboration_section). No Streamlit
    dependency — safe to call in tests and offline preview scripts.
    """
    parts = [_header_html(view["chips_html"])]
    if view["empty"]:
        parts.append(_empty_state_html(view["ticker"]))
        return "".join(parts)

    parts.append(_headline_reline_html(view["headline"], view["reline"]))
    parts.append(_two_col_html(view["stance_segments"], view["readout_rows"]))
    if view["claims_strong"]:
        parts.append(
            _claims_block_html(
                "Strong claims, verified & high reliability", view["claims_strong"]
            )
        )
    if view["claims_moderate"]:
        parts.append(_claims_block_html("Moderate claims", view["claims_moderate"]))
    if view["conflicted"]:
        parts.append(_conflicted_box_html())
    if view["show_dissent_callout"]:
        parts.append(_dissent_callout_html(view["dissent_claim"], view["tier"]))
    return "".join(parts)


# ---------------------------------------------------------------------------
# HTML builders (pure — no Streamlit, unit-testable)
# ---------------------------------------------------------------------------


def _header_html(chips_html: str) -> str:
    return (
        '<div id="sa-corroboration"></div>'
        '<hr style="border:none;border-top:1px solid var(--ri-hair);'
        'margin:18px 0 12px">'
        '<div class="sa-eyebrow" style="display:flex;align-items:center;'
        'justify-content:space-between;flex-wrap:wrap;gap:8px;">'
        "<span>&#9671; Corroboration &nbsp;"
        + render_info(
            "Independent claims from outside sources, each verified & weighted "
            "by reliability, then summarized into how much they converge. "
            "Convergence is agreement, not a forecast.",
            "src · corroboration store",
        )
        + "</span>"
        f'<span class="sa-chips">{chips_html}</span>'
        "</div>"
    )


def _headline_reline_html(headline: str, reline: str) -> str:
    return (
        f'<div class="sa-gname" style="margin:5px 0 2px">{_html.escape(headline)}</div>'
        f'<div style="font-size:12px;color:var(--ri-ink2);font-style:italic;'
        f'margin-bottom:10px;">{_html.escape(reline)}</div>'
    )


def _empty_state_html(ticker: str) -> str:
    label = f" for {ticker}" if ticker else ""
    return (
        '<div style="border:1px solid var(--ri-line);border-radius:9px;'
        'background:var(--ri-card);padding:16px;text-align:center;">'
        f'<div style="font-size:14px;color:#64748B;">No corroboration data{label}.</div>'
        '<div style="font-size:13px;color:#94A3B8;margin-top:4px;">'
        "Run <code>corroborate</code> to surface external evidence.</div>"
        "</div>"
    )


def _claim_card_html(claim: HarvestedClaim) -> str:
    """Full evidence card for a claim (strong or moderate)."""
    verified_badge = (
        '<span style="font-size:11px;font-weight:600;color:#16A34A;'
        "background:#DCFCE7;padding:2px 6px;border-radius:4px;margin-left:6px;"
        '">✓ VERIFIED</span>'
        if claim.verified
        else ""
    )
    freshness = f"{claim.published_at.isoformat()}"
    icon = _STANCE_ICON.get(claim.stance, "→")
    return (
        '<div class="sa-claim">'
        '<div style="flex:1;min-width:0;">'
        '<div style="display:flex;justify-content:space-between;align-items:center;'
        'flex-wrap:wrap;gap:4px;">'
        '<span style="font-weight:600;font-size:14px;color:#1A202C;">'
        f"{icon} {claim.source_name}</span>"
        f"{verified_badge}"
        f'<span style="font-size:11px;color:#94A3B8;">{freshness}</span>'
        "</div>"
        f'<div style="font-size:13px;color:#374151;margin-top:6px;">{claim.thesis_summary}</div>'
        f'<div style="margin-top:6px;">'
        f'<a href="{claim.url}" target="_blank" '
        f'style="font-size:12px;color:#0F6E80;">↗ Source</a></div>'
        "</div></div>"
    )


def _claim_row_html(claim: HarvestedClaim) -> str:
    """Compact row for a WEAK / unverified claim."""
    icon = _STANCE_ICON.get(claim.stance, "→")
    return (
        f'<div style="padding:6px 10px;border-bottom:1px solid #F1F5F9;font-size:13px;">'
        f'<span style="color:#0F6E80;font-weight:500;">{icon} {claim.source_name}</span> '
        f'<span style="color:#374151;">{claim.thesis_summary}</span> '
        f'<span style="color:#94A3B8;font-size:11px;">{claim.published_at.isoformat()}</span>'
        f"</div>"
    )


def _our_readout_html(readout: OurReadout) -> str:
    """Compact single-strip HTML block for an OurReadout (utility builder)."""
    fp = (
        f"{readout.factor_percentile:.0f}th"
        if readout.factor_percentile is not None
        else "N/A"
    )
    trend = readout.trend_health.value.upper() if readout.trend_health else "N/A"
    div_icon = "⚠" if readout.divergence_flag else "✓"
    disc = readout.discipline_flag or "—"
    trend_colour = {
        "HEALTHY": "#16A34A",
        "CAUTION": "#CA8A04",
        "BROKEN": "#DC2626",
    }.get(trend, "#64748B")
    return (
        '<div style="border:1px solid var(--ri-line);border-radius:9px;'
        'background:var(--ri-card);padding:9px 11px;margin-top:12px;">'
        '<div style="font-size:12px;color:#94A3B8;text-transform:uppercase;'
        'letter-spacing:0.8px;margin-bottom:8px;">Our model says</div>'
        '<div style="display:flex;gap:24px;flex-wrap:wrap;">'
        f'<span style="font-size:13px;"><b>Factor percentile:</b> {fp}</span>'
        f'<span style="font-size:13px;color:{trend_colour};"><b>Trend:</b> {trend}</span>'
        f'<span style="font-size:13px;"><b>Divergence:</b> {div_icon}</span>'
        f'<span style="font-size:13px;"><b>Discipline:</b> {disc}</span>'
        "</div></div>"
    )


def _stance_bar_html(segments: list[dict]) -> str:  # type: ignore[type-arg]
    """Single horizontal bar split into stance segments, widths reliability-weighted,
    labels headcount (mockup .sbar — not the old 3-row per-stance bars)."""
    visible = [s for s in segments if s["pct"] >= 0.5]
    if not visible:
        return (
            '<div style="font-size:11px;color:var(--ri-muted);text-transform:uppercase;'
            "font-family:'IBM Plex Mono',monospace;margin-bottom:8px;\">Where sources land</div>"
            '<div style="font-size:12px;color:#94A3B8;padding:8px 0;">'
            "Stance distribution — data gap (no weighted claims).</div>"
        )
    bar = "".join(
        f'<div style="width:{s["pct"]:.0f}%;background:{s["colour"]};'
        "display:flex;align-items:center;justify-content:center;"
        "font-family:'IBM Plex Mono',monospace;font-size:8.5px;font-weight:700;color:#fff;\">"
        f'{_html.escape(s["label"])} {s["count"]}</div>'
        for s in visible
    )
    legend = "".join(
        '<span style="margin-right:10px;">'
        f'<i style="display:inline-block;width:8px;height:8px;border-radius:2px;'
        f'margin-right:4px;vertical-align:middle;background:{s["colour"]};"></i>'
        f'{_html.escape(s["label"].capitalize())}</span>'
        for s in segments
    )
    return (
        '<div style="font-size:11px;color:var(--ri-muted);text-transform:uppercase;'
        "font-family:'IBM Plex Mono',monospace;margin-bottom:8px;\">Where sources land</div>"
        f'<div style="display:flex;height:22px;border-radius:5px;overflow:hidden;">{bar}</div>'
        f"<div style=\"display:flex;flex-wrap:wrap;margin-top:7px;font-family:'IBM Plex Mono',"
        f'monospace;font-size:8.5px;color:#566;">{legend}</div>'
        '<div style="font-size:11px;color:var(--ri-muted);margin-top:9px;font-style:italic;">'
        "Reliability-weighted, not a headcount &mdash; a weak source can&#39;t outvote a 10-K.</div>"
    )


def _readout_card_html(rows: list[tuple[str, str]]) -> str:
    """Two-column readout card ("Our readout — how the panels map")."""
    body = "".join(
        '<div style="display:flex;justify-content:space-between;font-size:11px;'
        'padding:3px 0;border-bottom:1px solid var(--ri-hair);">'
        f"<span>{_html.escape(lbl)}</span>"
        f"<b style=\"font-family:'IBM Plex Mono',monospace;color:var(--ri-ink);\">"
        f"{_html.escape(val)}</b></div>"
        for lbl, val in rows
    )
    return (
        '<div style="border:1px solid var(--ri-line);border-radius:9px;'
        'background:var(--ri-card);padding:10px 12px;">'
        "<div style=\"font-family:'IBM Plex Mono',monospace;font-size:9px;"
        'text-transform:uppercase;color:var(--ri-muted);margin-bottom:7px;">'
        "Our readout (how the panels map)</div>"
        f"{body}</div>"
    )


def _two_col_html(segments: list[dict], readout_rows: list[tuple[str, str]]) -> str:  # type: ignore[type-arg]
    return (
        '<div class="sa-pnl-two" style="margin:4px 0 14px;">'
        f"<div>{_stance_bar_html(segments)}</div>"
        f"<div>{_readout_card_html(readout_rows)}</div>"
        "</div>"
    )


def _dissent_callout_html(claim: HarvestedClaim | None, tier: ConvergenceTier) -> str:
    if claim is None:
        return ""
    return (
        '<div style="font-size:12px;color:#7a4a08;background:rgba(180,83,9,.06);'
        "border:1px solid rgba(180,83,9,.25);border-radius:7px;padding:9px 12px;"
        'margin-top:12px;">'
        "<b style=\"font-family:'IBM Plex Mono',monospace;\">&#9888; The dissent:</b> "
        f"{_html.escape(claim.source_name)} argues {_html.escape(claim.thesis_summary)} "
        f"&mdash; which is why convergence is <b>{tier.value}, not strong</b>. "
        "We surface it rather than average it away.</div>"
    )


def _conflicted_box_html() -> str:
    return (
        '<div style="border:1px solid var(--ri-line);border-radius:9px;'
        'background:var(--ri-card);border-left:3px solid #DC2626;padding:10px 14px;">'
        '<span style="font-weight:700;color:#DC2626;">⚠ CONFLICTED</span>'
        '<span style="font-size:13px;color:#64748B;margin-left:8px;">'
        "Sources disagree — treat with caution.</span></div>"
    )


def _directional_views_html(views: list[DirectionalView]) -> str:
    """HTML table for DirectionalView tilt detail (collapsed behind an expander)."""
    if not views:
        return ""
    rows = ""
    for v in views:
        colour = _TILT_COLOUR.get(v.tilt, "#64748B")
        stance_icon = _STANCE_ICON.get(v.net_stance, "→")
        rows += (
            f'<tr><td style="font-size:13px;padding:4px 8px;">{v.group_name}</td>'
            f'<td style="font-size:13px;padding:4px 8px;">{stance_icon} {v.net_stance.value}</td>'
            f'<td style="font-size:13px;padding:4px 8px;font-weight:700;color:{colour};">'
            f"{v.tilt}</td>"
            f'<td style="font-size:13px;padding:4px 8px;color:#94A3B8;">'
            f"{v.mean_convergence:.0%}</td></tr>"
        )
    return (
        '<table style="width:100%;border-collapse:collapse;">'
        "<thead><tr>"
        '<th style="font-size:11px;color:#94A3B8;text-align:left;padding:4px 8px;">Group</th>'
        '<th style="font-size:11px;color:#94A3B8;text-align:left;padding:4px 8px;">Stance</th>'
        '<th style="font-size:11px;color:#94A3B8;text-align:left;padding:4px 8px;">Tilt</th>'
        '<th style="font-size:11px;color:#94A3B8;text-align:left;padding:4px 8px;">Confidence</th>'
        f"</tr></thead><tbody>{rows}</tbody></table>"
    )


def _claims_block_html(title: str, claims: list[HarvestedClaim]) -> str:
    """Section header + full evidence cards for STRONG/MODERATE claim groups."""
    header = (
        f'<div class="sa-eyebrow" style="margin-top:12px;">'
        f"{_html.escape(title)} ({len(claims)})</div>"
    )
    cards = "".join(_claim_card_html(c) for c in claims)
    return header + cards


# ---------------------------------------------------------------------------
# Streamlit renderers (private — called only by render_corroboration_section)
# ---------------------------------------------------------------------------


def _render_weak_claims(claims: list[HarvestedClaim]) -> None:
    import streamlit as st

    if not claims:
        return
    with st.expander(
        f"Weak / unverified signals ({len(claims)}) — forum & blog, low reliability"
    ):
        for claim in claims:
            st.markdown(_claim_row_html(claim), unsafe_allow_html=True)


def _render_directional_views(views: list[DirectionalView]) -> None:
    import streamlit as st

    html = _directional_views_html(views)
    if not html:
        return
    with st.expander("Directional tilt detail"):
        st.markdown(html, unsafe_allow_html=True)
