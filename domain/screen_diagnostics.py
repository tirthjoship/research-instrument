"""Pure screen diagnostics + honesty verdict (stdlib only)."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class ScreenVerdict(Enum):
    UNDER_POWERED = "UNDER_POWERED"
    EARNED_ABSTENTION = "EARNED_ABSTENTION"
    HAS_CANDIDATES = "HAS_CANDIDATES"


@dataclass(frozen=True)
class ScreenDiagnostics:
    scanned: int
    had_history: int
    above_trend: int
    cleared: int

    def __post_init__(self) -> None:
        seq = [self.scanned, self.had_history, self.above_trend, self.cleared]
        if any(v < 0 for v in seq):
            raise ValueError("counts must be >= 0")
        if not (self.scanned >= self.had_history >= self.above_trend >= self.cleared):
            raise ValueError(
                "counts must be monotonically non-increasing through the funnel"
            )

    @property
    def history_coverage(self) -> float:
        return self.had_history / self.scanned if self.scanned else 0.0


def classify_screen(d: ScreenDiagnostics, coverage_floor: float) -> ScreenVerdict:
    if d.cleared > 0:
        return ScreenVerdict.HAS_CANDIDATES
    if d.history_coverage < coverage_floor:
        return ScreenVerdict.UNDER_POWERED
    return ScreenVerdict.EARNED_ABSTENTION
