"""Pattern memory service — pure domain logic.

Provides three capabilities:
1. build_patterns_from_outcomes  — aggregate TradeOutcomes into PatternEntries
2. compute_weight_adjustments    — adjust ConvictionWeights from SignalPerformance
3. discover_rules                — derive LearnedRules from reliable PatternEntries

Only stdlib + domain imports permitted (hexagonal architecture rule).
"""

from __future__ import annotations

import uuid
from dataclasses import fields as dc_fields
from datetime import date

from domain.conviction import ConvictionWeights
from domain.outcome import SignalPerformance, TradeOutcome
from domain.pattern_memory import LearnedRule, PatternEntry, WeightAdjustment

_MAX_WEIGHT = 3.0
_MIN_WEIGHT = 0.05
_BOOST_STEP = 0.2
_REDUCE_STEP = 0.2

# Map signal_name values to ConvictionWeights field names
_SIGNAL_TO_FIELD: dict[str, str] = {
    "signal_agreement": "signal_agreement",
    "smart_money": "smart_money",
    "sentiment_momentum": "sentiment_momentum",
    "fundamental_basis": "fundamental_basis",
    "temporal_freshness": "temporal_freshness",
    "ml_direction": "ml_direction",
}


def build_patterns_from_outcomes(outcomes: list[TradeOutcome]) -> list[PatternEntry]:
    """Group outcomes by sorted signal combination and compute aggregate stats.

    Args:
        outcomes: List of completed round-trip trade outcomes.

    Returns:
        One PatternEntry per unique signal combination.  Empty list if no outcomes.
    """
    if not outcomes:
        return []

    # Group by sorted tuple of signals
    groups: dict[tuple[str, ...], list[TradeOutcome]] = {}
    for outcome in outcomes:
        key = tuple(sorted(outcome.signals_at_entry))
        groups.setdefault(key, []).append(outcome)

    patterns: list[PatternEntry] = []
    for combo, group in groups.items():
        n = len(group)
        avg_return = sum(o.return_pct for o in group) / n
        hit_rate = sum(1 for o in group if o.is_profitable) / n
        avg_holding = int(sum(o.holding_days for o in group) / n)
        patterns.append(
            PatternEntry(
                signal_combination=combo,
                sector="any",
                market_condition="any",
                outcome_count=n,
                avg_return_pct=avg_return,
                hit_rate=hit_rate,
                avg_holding_days=avg_holding,
            )
        )
    return patterns


def compute_weight_adjustments(
    performances: list[SignalPerformance],
    current_weights: ConvictionWeights,
    min_trades: int = 10,
) -> list[WeightAdjustment]:
    """Compute per-dimension weight adjustments based on signal performance.

    Rules:
    - total_trades < min_trades → no change, reason = "Insufficient data"
    - hit_rate >= 65% → boost by min(BOOST_STEP, MAX - old), cap at MAX
    - hit_rate < 50%  → reduce by min(REDUCE_STEP, old - MIN), floor at MIN
    - otherwise       → no change, reason = "within normal range"

    Args:
        performances: Aggregated performance stats for each signal.
        current_weights: Current conviction weight values.
        min_trades: Minimum number of trades required before adjusting.

    Returns:
        List of WeightAdjustment records (one per recognised signal name).
    """
    today = date.today().isoformat()
    adjustments: list[WeightAdjustment] = []

    # Build lookup: field_name → current float value
    weight_values: dict[str, float] = {
        f.name: getattr(current_weights, f.name) for f in dc_fields(current_weights)
    }

    for perf in performances:
        field_name = _SIGNAL_TO_FIELD.get(perf.signal_name)
        if field_name is None:
            continue  # unknown signal — skip

        old = weight_values[field_name]

        if perf.total_trades < min_trades:
            adjustments.append(
                WeightAdjustment(
                    dimension=field_name,
                    old_weight=old,
                    new_weight=old,
                    reason="Insufficient data",
                    adjusted_date=today,
                )
            )
            continue

        if perf.hit_rate >= 65.0:
            delta = min(_BOOST_STEP, _MAX_WEIGHT - old)
            new = round(old + delta, 4)
            reason = f"Hit rate {perf.hit_rate:.1f}% >= 65% — boost applied"
        elif perf.hit_rate < 50.0:
            delta = min(_REDUCE_STEP, old - _MIN_WEIGHT)
            new = round(old - delta, 4)
            reason = f"Hit rate {perf.hit_rate:.1f}% < 50% — reduction applied"
        else:
            new = old
            reason = "Hit rate within normal range (50–65%)"

        adjustments.append(
            WeightAdjustment(
                dimension=field_name,
                old_weight=old,
                new_weight=new,
                reason=reason,
                adjusted_date=today,
            )
        )

    return adjustments


def discover_rules(patterns: list[PatternEntry]) -> list[LearnedRule]:
    """Derive actionable rules from reliable PatternEntries.

    A pattern is eligible only when ``is_reliable`` is True (outcome_count >= 10).

    Rule conditions:
    - hit_rate < 50%  → "suppress" rule, confidence = min(outcome_count / 30, 1.0)
    - hit_rate >= 65% AND avg_return_pct > 3% → "boost" rule,
      confidence = min(outcome_count / 20, 1.0)

    Args:
        patterns: PatternEntry objects to evaluate.

    Returns:
        List of LearnedRule objects.  Empty list if no eligible patterns.
    """
    today = date.today().isoformat()
    rules: list[LearnedRule] = []

    for pattern in patterns:
        if not pattern.is_reliable:
            continue

        hit_pct = pattern.hit_rate  # stored as 0.0–1.0 fraction

        if hit_pct < 0.50:
            confidence = min(pattern.outcome_count / 30, 1.0)
            action = "suppress"
            description = (
                f"Suppress signals {pattern.signal_combination}: "
                f"hit rate {hit_pct*100:.1f}% below 50% across "
                f"{pattern.outcome_count} outcomes"
            )
        elif hit_pct >= 0.65 and pattern.avg_return_pct > 3.0:
            confidence = min(pattern.outcome_count / 20, 1.0)
            action = "boost"
            description = (
                f"Boost signals {pattern.signal_combination}: "
                f"hit rate {hit_pct*100:.1f}% with avg return "
                f"{pattern.avg_return_pct:.2f}% across {pattern.outcome_count} outcomes"
            )
        else:
            continue  # middle range — no rule

        rules.append(
            LearnedRule(
                rule_id=str(uuid.uuid4()),
                description=description,
                signal_combination=pattern.signal_combination,
                sector=pattern.sector,
                action=action,
                confidence=round(confidence, 4),
                supporting_outcomes=pattern.outcome_count,
                learned_date=today,
            )
        )

    return rules
