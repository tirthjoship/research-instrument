"""Conviction scoring domain models.

Pure Python value objects — no external framework imports.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import Enum


class SmartMoneyType(str, Enum):
    """SEC filing type that sourced a smart-money signal."""

    FORM_13D = "13D"
    FORM_4 = "Form4"


class ActionType(str, Enum):
    """Recommended action for an opportunity card."""

    BUY = "BUY"
    WATCH = "WATCH"
    HOLD = "HOLD"
    SELL = "SELL"


class FreshnessLevel(str, Enum):
    """Age classification of the most recent signal."""

    FRESH = "fresh"  # < 4 hours
    RECENT = "recent"  # 4–24 hours
    STALE = "stale"  # > 24 hours


@dataclass(frozen=True)
class SmartMoneySignal:
    """An institutional or insider filing signal.

    Attributes:
        ticker: Ticker symbol.
        signal_type: SEC form that generated the signal.
        filer_name: Name of the filer (fund, insider).
        stake_pct: Ownership stake percentage, or None if not applicable.
        transaction_value: Dollar value of the transaction.
        filed_date: Filing date in YYYY-MM-DD format.
        is_activist: Whether the filer is an activist investor.
        source_url: Link to the SEC filing (optional).
        insider_role: Job title for Form 4 filers (optional).
        transaction_type: e.g. "Purchase", "Sale" for Form 4 (optional).
    """

    ticker: str
    signal_type: SmartMoneyType
    filer_name: str
    stake_pct: float | None
    transaction_value: float
    filed_date: str
    is_activist: bool
    source_url: str = ""
    insider_role: str = ""
    transaction_type: str = ""

    def __post_init__(self) -> None:
        if self.stake_pct is not None and self.stake_pct < 0:
            raise ValueError(
                f"stake_pct must be >= 0 if provided, got {self.stake_pct}"
            )


@dataclass(frozen=True)
class ConvictionWeights:
    """Relative weights for each sub-dimension of conviction.

    Defaults are calibrated from Phase 3B ablation results.
    """

    signal_agreement: float = 1.0
    smart_money: float = 1.5
    sentiment_momentum: float = 1.0
    fundamental_basis: float = 1.0
    temporal_freshness: float = 1.2
    ml_direction: float = 0.3
    event_signal: float = 1.0


_FRESH_THRESHOLD_HOURS = 4
_STALE_THRESHOLD_HOURS = 24


@dataclass(frozen=True)
class ConvictionScore:
    """Weighted conviction score for a single ticker.

    Attributes:
        ticker: Ticker symbol.
        score: Overall conviction score in [1.0, 10.0].
        sub_scores: Map of dimension name → raw component score.
        signals_firing: Count of independent signals that contributed.
        freshest_signal: Timestamp of the most recent contributing signal.
        explanation: Human-readable summary of why this score was generated.
    """

    ticker: str
    score: float
    sub_scores: dict[str, float]
    signals_firing: int
    freshest_signal: datetime
    explanation: str

    def __post_init__(self) -> None:
        if not 1.0 <= self.score <= 10.0:
            raise ValueError(f"score must be in [1.0, 10.0], got {self.score}")

    def freshness_level(self, now: datetime) -> FreshnessLevel:
        """Classify signal freshness relative to *now*.

        Thresholds:
            FRESH  — age < 4 hours
            RECENT — 4 hours <= age < 24 hours
            STALE  — age >= 24 hours
        """
        age_hours = (now - self.freshest_signal).total_seconds() / 3600
        if age_hours < _FRESH_THRESHOLD_HOURS:
            return FreshnessLevel.FRESH
        if age_hours < _STALE_THRESHOLD_HOURS:
            return FreshnessLevel.RECENT
        return FreshnessLevel.STALE


@dataclass(frozen=True)
class OpportunityCard:
    """A decision-oriented card surfaced in the dashboard Opportunities tab.

    Combines a conviction score with a plain-English narrative so the user
    can act without digging into raw numbers.

    Attributes:
        ticker: Ticker symbol.
        conviction: Numeric conviction value (mirrors conviction_score.score).
        action: Recommended action (BUY / WATCH / HOLD / SELL).
        alert_summary: One-sentence headline for the opportunity.
        evidence: Ordered list of supporting facts.
        suggestion: Actionable plain-English recommendation.
        risks: Key risks to monitor.
        generated_at: Timestamp when this card was created.
        conviction_score: Full ConvictionScore object for drill-down.
    """

    ticker: str
    conviction: float
    action: ActionType
    alert_summary: str
    evidence: list[str]
    suggestion: str
    risks: list[str]
    generated_at: datetime
    conviction_score: ConvictionScore
