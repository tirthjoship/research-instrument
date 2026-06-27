"""SP3 composite screener types — ScreenedRow wraps ScreenCandidate + optional corroboration."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from domain.corroboration_models import ConvergenceTier, Stance
from domain.screen_models import ScreenCandidate

TIER_RANK: dict[ConvergenceTier, float | None] = {
    ConvergenceTier.STRONG: 1.0,
    ConvergenceTier.MODERATE: 0.67,
    ConvergenceTier.WEAK: 0.33,
    ConvergenceTier.CONFLICTED: 0.0,
    ConvergenceTier.NONE: None,
}


@dataclass(frozen=True)
class CorroborationSnapshot:
    ticker: str
    convergence_tier: ConvergenceTier
    n_sources: int
    surfaced_at: date
    net_stance: Stance = Stance.NEUTRAL


@dataclass(frozen=True)
class ScreenedRow:
    candidate: ScreenCandidate
    corroboration: CorroborationSnapshot | None
    blended_percentile: float
    factor_only: bool


def blend(factor_pct: float, snap: CorroborationSnapshot | None) -> float:
    """Equal-weight rank-average of factor percentile and convergence tier rank.

    Returns factor_pct unchanged when no corroboration or tier is NONE.
    """
    if snap is None:
        return factor_pct
    tier_pct = TIER_RANK.get(snap.convergence_tier)
    if tier_pct is None:
        return factor_pct
    return 0.5 * factor_pct + 0.5 * tier_pct
