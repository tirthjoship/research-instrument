from dataclasses import dataclass, field
from enum import Enum


class ScreenLabel(Enum):
    VALIDATED = "VALIDATED"
    RESEARCH_ONLY = "RESEARCH_ONLY"


@dataclass(frozen=True)
class FactorScore:
    name: str
    value: float
    percentile: float
    contribution: float


@dataclass(frozen=True)
class ScreenCandidate:
    ticker: str
    composite: float
    factor_scores: tuple[FactorScore, ...]
    trend_health: float
    why: str
    label: ScreenLabel


@dataclass(frozen=True)
class ScreenResult:
    as_of: str
    candidates: tuple[ScreenCandidate, ...]
    universe_size: int
    regime: str
    scorecard_ref: str | None
    abstained: bool = field(default=False)

    def __post_init__(self) -> None:
        if self.universe_size < 0:
            raise ValueError("universe_size must be >= 0")
