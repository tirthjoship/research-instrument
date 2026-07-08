"""Corroboration — pure view builder (mirrors supply_chain_view.py's pattern).

Turns a ``CorroborationTabView`` (+ optional live ``OurReadout``) into a plain
dict the renderer (``corroboration_section.py``) can draw without doing any
convergence/dissent math itself. No Streamlit import — safe to unit test.

Convergence tier comes from the persisted ``CandidateSnapshot`` when present
(the same tier the corroboration store/CLI computed); only inferred from the
raw claims as a fallback when no snapshot exists. Convergence is an
evidence-agreement label, never a return forecast (ADR-062).
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from adapters.visualization.data_loader import CorroborationTabView

from adapters.visualization.components.status_chip import render_status_chip
from domain.corroboration_models import (
    ConvergenceTier,
    HarvestedClaim,
    OurReadout,
    Stance,
)

_OPPOSITE: dict[Stance, Stance] = {
    Stance.BULLISH: Stance.BEARISH,
    Stance.BEARISH: Stance.BULLISH,
}

_TIER_TONE: dict[ConvergenceTier, str] = {
    ConvergenceTier.STRONG: "green",
    ConvergenceTier.MODERATE: "petrol",
    ConvergenceTier.WEAK: "amber",
    ConvergenceTier.CONFLICTED: "crimson",
    ConvergenceTier.NONE: "grey",
}

_STANCE_SEGMENT_ORDER: tuple[tuple[Stance, str, str], ...] = (
    (Stance.BULLISH, "bullish", "#5aa86a"),
    (Stance.NEUTRAL, "neutral", "#c2ccce"),
    (Stance.BEARISH, "bearish", "#d39595"),
)

# Minimum credibility for a lone dissenting claim to earn its own callout —
# mirrors _group_claims_by_weight's "moderate" floor so a throwaway forum
# post can't trigger the amber box.
_DISSENT_CALLOUT_MIN_WEIGHT = 0.45


# ---------------------------------------------------------------------------
# Claim grouping (moved from corroboration_section.py; re-exported there for
# backward compatibility with existing tests)
# ---------------------------------------------------------------------------


def _group_claims_by_weight(
    claims: tuple[HarvestedClaim, ...] | list[HarvestedClaim],
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
# Alignment / dissent
# ---------------------------------------------------------------------------


def _infer_tier(n_align: int, total: int) -> ConvergenceTier:
    """Fallback tier when no persisted CandidateSnapshot exists for this ticker."""
    if total == 0:
        return ConvergenceTier.NONE
    ratio = n_align / total
    if ratio >= 0.80:
        return ConvergenceTier.STRONG
    if ratio >= 0.60:
        return ConvergenceTier.MODERATE
    if ratio >= 0.40:
        return ConvergenceTier.WEAK
    return ConvergenceTier.CONFLICTED


def _align_counts(
    claims: list[HarvestedClaim], net_stance: Stance
) -> tuple[int, int, int]:
    """(n_align, n_neutral, n_dissent). Dissent is strictly the *opposite* stance —
    a neutral claim (e.g. a 10-K risk disclosure) is not "dissent", it's a
    separate, honest third bucket. Matches the mockup's "4 align / 1 neutral /
    1 dissent" framing, not a binary agree/disagree split."""
    opposite = _OPPOSITE.get(net_stance)
    n_align = sum(1 for c in claims if c.stance == net_stance)
    n_dissent = sum(1 for c in claims if opposite is not None and c.stance == opposite)
    n_neutral = len(claims) - n_align - n_dissent
    return n_align, n_neutral, n_dissent


def _pick_dissent_claim(
    claims: list[HarvestedClaim], net_stance: Stance
) -> HarvestedClaim | None:
    """The single highest-reliability claim that opposes net_stance, if any."""
    opposite = _OPPOSITE.get(net_stance)
    if opposite is None:
        return None
    dissenters = [c for c in claims if c.stance == opposite]
    if not dissenters:
        return None
    return max(dissenters, key=lambda c: c.reliability_weight)


# ---------------------------------------------------------------------------
# Narrative copy (descriptive only — no invented topic/thesis detail)
# ---------------------------------------------------------------------------


def _headline(tier: ConvergenceTier, n_dissent: int) -> str:
    if tier == ConvergenceTier.STRONG:
        return "Outside evidence aligns"
    if tier == ConvergenceTier.MODERATE:
        if n_dissent == 1:
            return "Outside evidence mostly agrees — with one honest dissent"
        if n_dissent > 1:
            return f"Outside evidence mostly agrees — with {n_dissent} honest dissents"
        return "Outside evidence mostly agrees"
    if tier == ConvergenceTier.WEAK:
        return "Outside evidence offers limited signal"
    if tier == ConvergenceTier.CONFLICTED:
        return "Sources disagree — treat with caution"
    return "No outside evidence yet"


def _reline(
    total: int, n_align: int, n_neutral: int, n_dissent: int, tier: ConvergenceTier
) -> str:
    parts = [f"{n_align} align"]
    if n_neutral:
        parts.append(f"{n_neutral} neutral")
    if n_dissent:
        parts.append(f"{n_dissent} dissent{'s' if n_dissent != 1 else ''}")
    src_word = "source" if total == 1 else "sources"
    return (
        f"Of {total} independent {src_word}, {', '.join(parts)}. "
        f"Weighted by reliability, that's {tier.value} convergence."
    )


# ---------------------------------------------------------------------------
# Chips / stance bar / readout rows
# ---------------------------------------------------------------------------


def _chips_html(tier: ConvergenceTier, n_align: int, total: int, n_dissent: int) -> str:
    tone = _TIER_TONE.get(tier, "grey")
    chips = render_status_chip(
        tier.value.upper(),
        f"{n_align} of {total} align",
        tone=tone,
        rule=(
            f"{tier.value.upper()} = weighted agreement across {total} independent "
            "source(s) — agreement, not a forecast."
        ),
    )
    if n_dissent > 0:
        chips += render_status_chip(
            "dissent",
            str(n_dissent),
            tone="amber",
            rule=(
                f"{n_dissent} credible source(s) disagree — shown, not buried; "
                "disagreement is signal about confidence."
            ),
        )
    return chips


def _stance_segments(claims: list[HarvestedClaim]) -> list[dict[str, Any]]:
    total_w = sum(c.reliability_weight for c in claims)
    segments: list[dict[str, Any]] = []
    for stance, label, colour in _STANCE_SEGMENT_ORDER:
        n = sum(1 for c in claims if c.stance == stance)
        w = sum(c.reliability_weight for c in claims if c.stance == stance)
        pct = (w / total_w * 100.0) if total_w > 0 else 0.0
        segments.append(
            {
                "stance": stance.value,
                "label": label,
                "colour": colour,
                "count": n,
                "pct": pct,
            }
        )
    return segments


def _readout_rows(readout: OurReadout | None) -> list[tuple[str, str]]:
    if readout is None:
        return [
            ("Factor percentile", "—"),
            ("Trend health", "—"),
            ("Divergence flag", "—"),
            ("Discipline flag", "—"),
        ]
    fp = (
        f"{readout.factor_percentile:.0f}th"
        if readout.factor_percentile is not None
        else "—"
    )
    trend = readout.trend_health.value if readout.trend_health is not None else "—"
    divergence = "flagged" if readout.divergence_flag else "none"
    discipline = readout.discipline_flag or "—"
    return [
        ("Factor percentile", fp),
        ("Trend health", trend),
        ("Divergence flag", divergence),
        ("Discipline flag", discipline),
    ]


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------


def build_corroboration_view(
    corr: "CorroborationTabView | None",
    *,
    our_readout: OurReadout | None = None,
) -> dict[str, Any]:
    """Build the pure view-model dict consumed by ``render_corroboration_section``."""
    if corr is None or not corr.claims:
        ticker = corr.ticker if corr is not None else ""
        label = f" for {ticker}" if ticker else ""
        return {
            "empty": True,
            "ticker": ticker,
            "tier": ConvergenceTier.NONE,
            "chips_html": render_status_chip(
                "DATA GAP",
                "0 sources",
                tone="grey",
                rule=(
                    "No harvested corroboration claims in the store yet"
                    f"{label}. Harvest is search-driven and capped — not every "
                    "ticker appears every run."
                ),
            ),
            "headline": "No outside evidence yet — this section cross-checks our panels",
            "reline": (
                "Corroboration gathers independent claims (analyst notes, filings, "
                "trade press), verifies each citation, weights by source reliability, "
                "then summarizes how much outside reads agree with our factor/trend/"
                "discipline view. Convergence measures evidence agreement — not a "
                "return forecast (ADR-062)."
            ),
            "stance_segments": [],
            "readout_rows": _readout_rows(our_readout),
            "claims_strong": [],
            "claims_moderate": [],
            "claims_weak": [],
            "dissent_claim": None,
            "show_dissent_callout": False,
            "conflicted": False,
            "directional_views": (
                list(corr.directional_views) if corr is not None else []
            ),
        }

    claims = list(corr.claims)
    total = len(claims)
    net_stance = (
        corr.directional_views[0].net_stance
        if corr.directional_views
        else Stance.NEUTRAL
    )
    n_align, n_neutral, n_dissent = _align_counts(claims, net_stance)
    tier = (
        corr.snapshot.convergence
        if corr.snapshot is not None
        else _infer_tier(n_align, total)
    )
    strong, moderate, weak = _group_claims_by_weight(claims)
    dissent_claim = _pick_dissent_claim(claims, net_stance)
    show_dissent_callout = (
        tier in (ConvergenceTier.MODERATE, ConvergenceTier.WEAK)
        and dissent_claim is not None
        and dissent_claim.reliability_weight >= _DISSENT_CALLOUT_MIN_WEIGHT
    )

    return {
        "empty": False,
        "ticker": corr.ticker,
        "tier": tier,
        "n_align": n_align,
        "n_neutral": n_neutral,
        "n_dissent": n_dissent,
        "total": total,
        "chips_html": _chips_html(tier, n_align, total, n_dissent),
        "headline": _headline(tier, n_dissent),
        "reline": _reline(total, n_align, n_neutral, n_dissent, tier),
        "stance_segments": _stance_segments(claims),
        "readout_rows": _readout_rows(our_readout),
        "claims_strong": strong,
        "claims_moderate": moderate,
        "claims_weak": weak,
        "dissent_claim": dissent_claim,
        "show_dissent_callout": show_dissent_callout,
        "conflicted": tier == ConvergenceTier.CONFLICTED,
        "directional_views": list(corr.directional_views),
    }
