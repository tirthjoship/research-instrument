"""SP5 gate types and evaluation logic — pure stdlib, no external imports."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Literal

from domain.bootstrap import moving_block_bootstrap


@dataclass(frozen=True)
class GateSample:
    ticker: str
    snapshot_date: date
    resolved_at: date
    excess_21d: float  # ticker 21d return − SPY 21d return
    excess_63d: float | None  # None if <63d elapsed at resolution time
    beat_spy_21d: bool


@dataclass(frozen=True)
class GateResult:
    n_resolved: int
    mean_excess_21d: float
    ci_lower: float  # block-bootstrap 95% CI lower bound on mean excess
    ci_upper: float
    hit_rate_21d: float  # fraction of samples where beat_spy_21d is True
    mean_excess_63d: float | None
    verdict: Literal["PENDING", "PASS", "FAIL"]
    evaluated_at: date


def evaluate_gate(
    samples: list[GateSample],
    evaluated_at: date,
    min_n: int = 30,
    economic_bar: float = 0.005,
) -> GateResult:
    """Evaluate Hypothesis #9 gate. PENDING if n < min_n.
    PASS if bootstrap 95% CI lower bound > 0 AND mean_excess_21d >= economic_bar.
    FAIL otherwise (permanent — see ADR-064).
    """
    n = len(samples)
    excesses = [s.excess_21d for s in samples]
    mean_excess = sum(excesses) / n if n > 0 else 0.0

    bs = moving_block_bootstrap(excesses)
    _ci_low: object = bs["ci_low"]
    _ci_high: object = bs["ci_high"]
    ci_lower = float(_ci_low) if isinstance(_ci_low, (int, float)) else 0.0
    ci_upper = float(_ci_high) if isinstance(_ci_high, (int, float)) else 0.0

    hit_rate = sum(1 for s in samples if s.beat_spy_21d) / n if n > 0 else 0.0

    excesses_63 = [s.excess_63d for s in samples if s.excess_63d is not None]
    mean_excess_63d: float | None = (
        sum(excesses_63) / len(excesses_63) if excesses_63 else None
    )

    if n < min_n:
        verdict: Literal["PENDING", "PASS", "FAIL"] = "PENDING"
    elif ci_lower > 0 and mean_excess >= economic_bar:
        verdict = "PASS"
    else:
        verdict = "FAIL"

    return GateResult(
        n_resolved=n,
        mean_excess_21d=mean_excess,
        ci_lower=ci_lower,
        ci_upper=ci_upper,
        hit_rate_21d=hit_rate,
        mean_excess_63d=mean_excess_63d,
        verdict=verdict,
        evaluated_at=evaluated_at,
    )
