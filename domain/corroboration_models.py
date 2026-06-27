# domain/corroboration_models.py
"""Domain types for the corroboration engine. Stdlib-only (hexagonal rule)."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from enum import Enum


class Stance(Enum):
    BULLISH = "bullish"
    BEARISH = "bearish"
    NEUTRAL = "neutral"


class ConvergenceTier(Enum):
    STRONG = "strong"
    MODERATE = "moderate"
    WEAK = "weak"
    CONFLICTED = "conflicted"
    NONE = "none"


class TrendHealth(Enum):
    HEALTHY = "healthy"
    CAUTION = "caution"
    BROKEN = "broken"


@dataclass(frozen=True)
class HarvestedClaim:
    source_name: str
    ticker: str
    stance: Stance
    thesis_summary: str
    url: str
    published_at: date
    verified: bool
    reliability_weight: float


@dataclass(frozen=True)
class OurReadout:
    factor_percentile: float | None  # 0-100, our EvidenceScreen rank
    trend_health: TrendHealth | None
    divergence_flag: bool
    discipline_flag: str | None  # "REDUCE"/"HOLD"/"ADD_OK" if held


@dataclass(frozen=True)
class Agreement:
    n_bullish: int
    n_bearish: int
    weighted_score: float  # [-1, 1]
    our_alignment: str  # "AGREES"/"DIVERGES"/"NEUTRAL"


@dataclass(frozen=True)
class Uncertainty:
    coverage_n: int
    conflict: bool
    freshness_days: int  # age of newest source vs as_of


@dataclass(frozen=True)
class CorroboratedCandidate:
    ticker: str
    as_of: date
    sources: tuple[HarvestedClaim, ...]
    our_readout: OurReadout
    convergence: ConvergenceTier
    mean_convergence: float  # 0-1 numeric tier score for surfacing sort
    agreement: Agreement
    uncertainty: Uncertainty
    held: bool
    verification: str  # "ALL_VERIFIED"/"PARTIAL"/"NONE_DROPPED"


@dataclass(frozen=True)
class DirectionalView:
    group_kind: str  # "theme" or "sector"
    group_name: str
    net_stance: Stance
    mean_convergence: float  # 0-1 numeric tier mean
    your_exposure_pct: float
    evidence_weight_pct: float
    tilt: str  # "LEAN_IN"/"HOLD"/"LEAN_OUT"/"AVOID"


@dataclass(frozen=True)
class CandidateSnapshot:
    """Lightweight projection of CorroboratedCandidate for persistence and surfacing."""

    ticker: str
    convergence: ConvergenceTier
    verification: str  # "ALL_VERIFIED" | "PARTIAL" | "NONE_DROPPED"
    mean_convergence: float  # 0-1


@dataclass(frozen=True)
class DiscoveredEntry:
    """A ticker admitted to the corroboration overlay universe."""

    ticker: str
    company_name: str
    sector: str
    first_seen: date  # date of first admission to discovered universe
    last_seen: date  # date of most-recent STRONG/MODERATE corroboration
    convergence: ConvergenceTier
