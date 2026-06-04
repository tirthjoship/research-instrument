"""Pattern memory domain models.

Pure Python value objects — no external framework imports.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class PatternEntry:
    """An immutable record of a historical signal-pattern and its outcomes.

    Attributes:
        signal_combination: Tuple of signal names that fired together.
        sector: Market sector this pattern applies to.
        market_condition: Market regime (e.g. "bull", "bear", "neutral").
        outcome_count: Number of observed outcomes for this pattern.
        avg_return_pct: Average percentage return across outcomes.
        hit_rate: Fraction of outcomes that were profitable (0.0–1.0).
        avg_holding_days: Average number of days positions were held.
    """

    signal_combination: tuple[str, ...]
    sector: str
    market_condition: str
    outcome_count: int
    avg_return_pct: float
    hit_rate: float
    avg_holding_days: int

    @property
    def is_reliable(self) -> bool:
        """True when there are at least 10 observed outcomes."""
        return self.outcome_count >= 10

    @property
    def pattern_key(self) -> str:
        """Canonical key: sorted signals joined by '+', then sector, then condition."""
        sorted_signals = "+".join(sorted(self.signal_combination))
        return f"{sorted_signals}|{self.sector}|{self.market_condition}"


@dataclass(frozen=True)
class WeightAdjustment:
    """An immutable record of a conviction weight change for one dimension.

    Attributes:
        dimension: Name of the conviction dimension being adjusted.
        old_weight: Weight before adjustment.
        new_weight: Weight after adjustment.
        reason: Human-readable explanation for the change.
        adjusted_date: Date of adjustment in YYYY-MM-DD format.
    """

    dimension: str
    old_weight: float
    new_weight: float
    reason: str
    adjusted_date: str

    @property
    def change(self) -> float:
        """Rounded difference: new_weight − old_weight."""
        return round(self.new_weight - self.old_weight, 4)

    @property
    def direction(self) -> str:
        """'increased', 'decreased', or 'unchanged'."""
        delta = self.new_weight - self.old_weight
        if delta > 0:
            return "increased"
        if delta < 0:
            return "decreased"
        return "unchanged"


@dataclass(frozen=True)
class LearnedRule:
    """An immutable rule derived from observed signal patterns.

    Attributes:
        rule_id: Unique identifier for this rule.
        description: Human-readable summary of what the rule does.
        signal_combination: Signals that trigger this rule.
        sector: Market sector this rule applies to.
        action: Effect to apply — "suppress", "boost", or "warn".
        confidence: Rule confidence score in [0.0, 1.0].
        supporting_outcomes: Number of outcomes that support this rule.
        learned_date: Date rule was derived in YYYY-MM-DD format.
    """

    rule_id: str
    description: str
    signal_combination: tuple[str, ...]
    sector: str
    action: str
    confidence: float
    supporting_outcomes: int
    learned_date: str

    @property
    def is_high_confidence(self) -> bool:
        """True when confidence is at least 0.7."""
        return self.confidence >= 0.7
