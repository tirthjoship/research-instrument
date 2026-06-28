"""Corroboration evidence section — renders HarvestedClaims, OurReadout, DirectionalView."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from adapters.visualization.data_loader import CorroborationTabView

from domain.corroboration_models import (
    ConvergenceTier,
    DirectionalView,
    HarvestedClaim,
    OurReadout,
    Stance,
)

_TIER_COLOUR: dict[str, str] = {
    "strong": "#16A34A",
    "moderate": "#2563EB",
    "weak": "#CA8A04",
    "conflicted": "#DC2626",
    "none": "#94A3B8",
}

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


def render_corroboration_section(view: "CorroborationTabView | None") -> None:
    """Render the full corroboration section. Handles empty state gracefully."""
    import streamlit as st

    st.markdown('<div id="sa-corroboration"></div>', unsafe_allow_html=True)
    st.divider()
    st.markdown("#### Corroboration Evidence")
    if view is None or not view.claims:
        ticker = view.ticker if view is not None else ""
        st.markdown(_empty_state_html(ticker), unsafe_allow_html=True)
        return
    # D13: reliability-weighted stance distribution + convergence chip
    st.markdown(_weighted_stance_html(list(view.claims)), unsafe_allow_html=True)
    _net_stance = (
        view.directional_views[0].net_stance
        if view.directional_views
        else Stance.NEUTRAL
    )
    _conv_tier = view.snapshot.convergence if view.snapshot is not None else None
    chip = _convergence_chip_html(list(view.claims), _net_stance, _conv_tier)
    if chip:
        st.markdown(chip, unsafe_allow_html=True)

    strong, moderate, weak = _group_claims_by_weight(view.claims)
    _render_strong_claims(strong)
    _render_moderate_claims(moderate)
    _render_weak_claims(weak)
    if (
        view.snapshot is not None
        and view.snapshot.convergence == ConvergenceTier.CONFLICTED
    ):
        st.markdown(
            '<div style="border:1px solid var(--ri-line);border-radius:9px;'
            'background:var(--ri-card);border-left:3px solid #DC2626;padding:10px 14px;">'
            '<span style="font-weight:700;color:#DC2626;">⚠ CONFLICTED</span>'
            '<span style="font-size:13px;color:#64748B;margin-left:8px;">'
            "Sources disagree — treat with caution.</span></div>",
            unsafe_allow_html=True,
        )
    _render_our_readout(view.our_readout)
    _render_directional_views(list(view.directional_views))


# ---------------------------------------------------------------------------
# Claim grouping (pure — no Streamlit)
# ---------------------------------------------------------------------------


def _group_claims_by_weight(
    claims: tuple[HarvestedClaim, ...],
) -> tuple[list[HarvestedClaim], list[HarvestedClaim], list[HarvestedClaim]]:
    """Split claims into (strong, moderate, weak) buckets by verified + weight."""
    strong: list[HarvestedClaim] = []
    moderate: list[HarvestedClaim] = []
    weak: list[HarvestedClaim] = []
    for c in claims:
        if c.verified and c.reliability_weight >= 0.70:
            strong.append(c)
        elif c.verified or c.reliability_weight >= 0.45:
            moderate.append(c)
        else:
            weak.append(c)
    return strong, moderate, weak


# ---------------------------------------------------------------------------
# HTML builders (pure — no Streamlit, unit-testable)
# ---------------------------------------------------------------------------


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
    """Full evidence card for a STRONG (verified, high-weight) claim."""
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
        f'<div style="display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;gap:4px;">'
        f'<span style="font-weight:600;font-size:14px;color:#1A202C;">'
        f"{icon} {claim.source_name}</span>"
        f"{verified_badge}"
        f'<span style="font-size:11px;color:#94A3B8;">{freshness}</span>'
        f"</div>"
        f'<div style="font-size:13px;color:#374151;margin-top:6px;">{claim.thesis_summary}</div>'
        f'<div style="margin-top:6px;">'
        f'<a href="{claim.url}" target="_blank" '
        f'style="font-size:12px;color:#0F6E80;">↗ Source</a></div>'
        "</div></div>"
    )


def _claim_row_html(claim: HarvestedClaim) -> str:
    """Compact row for a MODERATE claim."""
    icon = _STANCE_ICON.get(claim.stance, "→")
    return (
        f'<div style="padding:6px 10px;border-bottom:1px solid #F1F5F9;font-size:13px;">'
        f'<span style="color:#0F6E80;font-weight:500;">{icon} {claim.source_name}</span> '
        f'<span style="color:#374151;">{claim.thesis_summary}</span> '
        f'<span style="color:#94A3B8;font-size:11px;">{claim.published_at.isoformat()}</span>'
        f"</div>"
    )


def _our_readout_html(readout: OurReadout) -> str:
    """HTML block for OurReadout bridge."""
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


def _weighted_stance_html(
    claims: list[HarvestedClaim] | tuple[HarvestedClaim, ...]
) -> str:
    """Reliability-weighted stance distribution bar (pure — no Streamlit).

    Aggregates ``reliability_weight`` by stance and renders percentage bars.
    Caption: "reliability-weighted — a weak source can't outvote a 10-K."
    Empty or zero-weight list → data-gap message.
    """
    if not claims:
        return (
            '<div style="font-size:13px;color:#94A3B8;padding:8px 0;">'
            "Stance distribution — data gap (no sources loaded).</div>"
        )
    total_w = sum(c.reliability_weight for c in claims)
    if total_w == 0.0:
        return (
            '<div style="font-size:13px;color:#94A3B8;padding:8px 0;">'
            "Stance distribution — data gap (zero weight).</div>"
        )

    bull_w = sum(c.reliability_weight for c in claims if c.stance == Stance.BULLISH)
    bear_w = sum(c.reliability_weight for c in claims if c.stance == Stance.BEARISH)
    neut_w = sum(c.reliability_weight for c in claims if c.stance == Stance.NEUTRAL)

    rows = ""
    for lbl, weight, colour in [
        ("▲ Constructive", bull_w, "#16A34A"),
        ("→ Neutral", neut_w, "#64748B"),
        ("▼ Cautious", bear_w, "#DC2626"),
    ]:
        pct = weight / total_w * 100
        if pct < 0.5:
            continue
        rows += (
            f'<div style="display:flex;align-items:center;gap:8px;margin-bottom:4px;">'
            f'<span style="font-size:12px;color:{colour};min-width:108px;">{lbl}</span>'
            f'<div style="flex:1;background:#F1F5F9;border-radius:4px;height:8px;">'
            f'<div style="background:{colour};width:{pct:.0f}%;height:8px;'
            f'border-radius:4px;opacity:0.78;"></div></div>'
            f'<span style="font-size:12px;color:#374151;min-width:34px;">'
            f"{pct:.0f}%</span>"
            f"</div>"
        )

    return (
        '<div style="border:1px solid var(--ri-line);border-radius:9px;'
        'background:var(--ri-card);padding:9px 11px;margin-bottom:8px;">'
        '<div style="font-size:11px;color:#94A3B8;text-transform:uppercase;'
        'letter-spacing:0.6px;margin-bottom:6px;">Stance distribution</div>'
        f"{rows}"
        '<div style="font-size:11px;color:#94A3B8;margin-top:6px;font-style:italic;">'
        "reliability-weighted — a weak source can&#39;t outvote a 10-K.</div>"
        "</div>"
    )


def _convergence_chip_html(
    claims: list[HarvestedClaim] | tuple[HarvestedClaim, ...],
    net_stance: Stance,
    convergence_tier: ConvergenceTier | None = None,
) -> str:
    """Compact chip: TIER·N-of-M / K-dissent (pure — no Streamlit).

    Parameters
    ----------
    claims:
        All claims for this ticker.
    net_stance:
        The overall net stance (used to count agreement vs dissent).
    convergence_tier:
        Optional explicit tier; when None the tier is inferred from the N/M ratio.

    Tone is grey/petrol — descriptive.  Convergence is NOT a forecast.
    """
    total_m = len(claims)
    if total_m == 0:
        return ""

    n_agree = sum(1 for c in claims if c.stance == net_stance)
    k_dissent = total_m - n_agree

    if convergence_tier is not None:
        tier_lbl = convergence_tier.value.upper()
        tier_colour = _TIER_COLOUR.get(convergence_tier.value, "#64748B")
    else:
        ratio = n_agree / total_m
        if ratio >= 0.80:
            tier_lbl, tier_colour = "STRONG", _TIER_COLOUR["strong"]
        elif ratio >= 0.60:
            tier_lbl, tier_colour = "MODERATE", _TIER_COLOUR["moderate"]
        elif ratio >= 0.40:
            tier_lbl, tier_colour = "WEAK", _TIER_COLOUR["weak"]
        else:
            tier_lbl, tier_colour = "CONFLICTED", _TIER_COLOUR["conflicted"]

    dissent_note = f"{k_dissent} dissent"
    return (
        f'<span class="sa-chip" style="font-size:11px;font-weight:600;'
        f"color:{tier_colour};background:#F8FAFC;border:1px solid {tier_colour}40;"
        f'border-radius:4px;padding:2px 8px;margin-right:6px;">'
        f"{tier_lbl}·{n_agree}-of-{total_m} / {dissent_note}</span>"
    )


def _directional_views_html(views: list[DirectionalView]) -> str:
    """HTML table for DirectionalView tilt panel."""
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
        '<div style="border:1px solid var(--ri-line);border-radius:9px;'
        'background:var(--ri-card);padding:9px 11px;margin-top:12px;">'
        '<div style="font-size:12px;color:#94A3B8;text-transform:uppercase;'
        'letter-spacing:0.8px;margin-bottom:8px;">Directional tilt</div>'
        '<table style="width:100%;border-collapse:collapse;">'
        "<thead><tr>"
        '<th style="font-size:11px;color:#94A3B8;text-align:left;padding:4px 8px;">Group</th>'
        '<th style="font-size:11px;color:#94A3B8;text-align:left;padding:4px 8px;">Stance</th>'
        '<th style="font-size:11px;color:#94A3B8;text-align:left;padding:4px 8px;">Tilt</th>'
        '<th style="font-size:11px;color:#94A3B8;text-align:left;padding:4px 8px;">Confidence</th>'
        f"</tr></thead><tbody>{rows}</tbody></table></div>"
    )


# ---------------------------------------------------------------------------
# Streamlit renderers (private — called only by render_corroboration_section)
# ---------------------------------------------------------------------------


def _render_strong_claims(claims: list[HarvestedClaim]) -> None:
    import streamlit as st

    if not claims:
        return
    st.markdown(
        f'<div style="font-size:12px;font-weight:700;color:#16A34A;'
        'text-transform:uppercase;letter-spacing:0.6px;margin-top:8px;">'
        f"Strong evidence ({len(claims)})</div>",
        unsafe_allow_html=True,
    )
    for claim in claims:
        st.markdown(_claim_card_html(claim), unsafe_allow_html=True)


def _render_moderate_claims(claims: list[HarvestedClaim]) -> None:
    import streamlit as st

    if not claims:
        return
    st.markdown(
        f'<div style="font-size:12px;font-weight:700;color:#2563EB;'
        'text-transform:uppercase;letter-spacing:0.6px;margin-top:8px;">'
        f"Moderate signals ({len(claims)})</div>",
        unsafe_allow_html=True,
    )
    for claim in claims:
        st.markdown(_claim_row_html(claim), unsafe_allow_html=True)


def _render_weak_claims(claims: list[HarvestedClaim]) -> None:
    import streamlit as st

    if not claims:
        return
    with st.expander(f"Weak / unverified signals ({len(claims)})"):
        for claim in claims:
            st.markdown(_claim_row_html(claim), unsafe_allow_html=True)


def _render_our_readout(readout: OurReadout | None) -> None:
    import streamlit as st

    if readout is None:
        return
    st.markdown(_our_readout_html(readout), unsafe_allow_html=True)


def _render_directional_views(views: list[DirectionalView]) -> None:
    import streamlit as st

    html = _directional_views_html(views)
    if html:
        st.markdown(html, unsafe_allow_html=True)
