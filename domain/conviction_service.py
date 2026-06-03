"""Conviction scoring service — pure functions, no I/O.

All logic is stateless and side-effect-free. Only stdlib imports.
"""

from __future__ import annotations

from dataclasses import fields
from datetime import datetime

from domain.conviction import ActionType, ConvictionScore, ConvictionWeights


def compute_freshness_score(signal_time: datetime, now: datetime) -> float:
    """Map signal age to a freshness score.

    Buckets:
        < 4 hours   → 10.0
        4–24 hours  → 8.0
        1–3 days    → 6.0
        3–7 days    → 4.0
        > 7 days    → 2.0
    """
    age_hours = (now - signal_time).total_seconds() / 3600.0
    if age_hours < 4:
        return 10.0
    if age_hours < 24:
        return 8.0
    if age_hours < 72:  # 3 days
        return 6.0
    if age_hours < 168:  # 7 days
        return 4.0
    return 2.0


def determine_action(score: float, is_bullish: bool) -> ActionType:
    """Map a conviction score + direction to a recommended action.

    Rules:
        score >= 7.0 and bullish  → BUY
        score >= 7.0 and bearish  → SELL
        otherwise                 → WATCH
    """
    if score >= 7.0:
        return ActionType.BUY if is_bullish else ActionType.SELL
    return ActionType.WATCH


def compute_conviction(
    sub_scores: dict[str, float], weights: ConvictionWeights
) -> float:
    """Compute a weighted average conviction score from component sub-scores.

    Only sub_scores keys that match ConvictionWeights field names are used.
    Keys present in sub_scores but absent from weights are ignored.

    Returns a value clamped to [1.0, 10.0].
    If total weight sums to zero (no matching keys), returns 1.0.
    """
    weight_map: dict[str, float] = {
        f.name: getattr(weights, f.name) for f in fields(weights)
    }

    total_weight = 0.0
    weighted_sum = 0.0
    for key, score in sub_scores.items():
        w = weight_map.get(key, 0.0)
        if w == 0.0:
            continue
        weighted_sum += score * w
        total_weight += w

    if total_weight == 0.0:
        return 1.0

    raw = weighted_sum / total_weight
    return max(1.0, min(10.0, raw))


def rank_opportunities(
    scores: list[ConvictionScore],
    top_n: int = 15,
    pinned: set[str] | None = None,
    min_score: float = 3.0,
) -> list[ConvictionScore]:
    """Rank conviction scores and return the top opportunities.

    Algorithm:
        1. Separate pinned tickers from the rest.
        2. Filter non-pinned by min_score.
        3. Sort remaining descending by score.
        4. Take up to top_n.
        5. Append any pinned tickers that didn't make the cut (preserving
           their original relative order for determinism).
    """
    if not scores:
        return []

    pinned = pinned or set()

    pinned_scores: list[ConvictionScore] = []
    eligible: list[ConvictionScore] = []

    for cs in scores:
        if cs.ticker in pinned:
            pinned_scores.append(cs)
        elif cs.score >= min_score:
            eligible.append(cs)

    eligible.sort(key=lambda c: c.score, reverse=True)
    top = eligible[:top_n]

    top_tickers = {c.ticker for c in top}
    missed_pinned = [c for c in pinned_scores if c.ticker not in top_tickers]

    return top + missed_pinned
