# domain/surfaced_call.py
"""Paper-call models for the opportunity forward-tracking engine. Pure domain."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import Enum


class OpportunityDirection(Enum):
    BUY = "buy"  # a surfaced emerging opportunity
    SELL_WATCH = "sell_watch"  # a held name surfacing with deteriorating signals


class Horizon(Enum):
    W1 = 7  # calendar days
    M1 = 30
    M3 = 90


def make_call_id(ticker: str, surfaced_at: datetime) -> str:
    return f"{ticker}_{surfaced_at:%Y%m%d}"


@dataclass(frozen=True)
class EvidenceItem:
    dimension: str
    score: float
    note: str


@dataclass(frozen=True)
class SurfacedCall:
    call_id: str
    ticker: str
    surfaced_at: datetime  # tz-aware; POINT-IN-TIME ANCHOR
    conviction: float
    divergence_score: float
    direction: OpportunityDirection
    evidence: tuple[EvidenceItem, ...]
    theme: str | None
    cap_tier: str
    spy_at_surface: float
    ndx_at_surface: float

    def __post_init__(self) -> None:
        if self.surfaced_at.tzinfo is None:
            raise ValueError("surfaced_at must be timezone-aware")
        for name, val in (
            ("conviction", self.conviction),
            ("divergence_score", self.divergence_score),
        ):
            if not 0.0 <= val <= 10.0:
                raise ValueError(f"{name} must be in [0, 10], got {val}")


@dataclass(frozen=True)
class CallOutcome:
    call_id: str
    horizon: Horizon
    resolved_at: datetime
    entry_price: float
    exit_price: float
    forward_return: float
    spy_return: float
    ndx_return: float
    beat_spy: bool
    beat_ndx: bool
    beat_both: bool
