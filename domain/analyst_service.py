"""Analyst track-record scoring. Pure functions, no I/O."""

from __future__ import annotations

from datetime import datetime
from typing import Callable

from domain.analyst import AnalystAction, AnalystRating


def score_firm_accuracy(
    events: list[AnalystRating],
    forward_return_fn: Callable[[AnalystRating], float],
    min_calls: int = 10,
) -> dict[str, float]:
    """Per-firm directional hit rate of past calls. Firms with fewer than
    `min_calls` directional calls get the neutral 0.5 (insufficient evidence).
    MAINTAIN events carry no direction and are skipped."""
    hits: dict[str, int] = {}
    total: dict[str, int] = {}
    for ev in events:
        if ev.action == AnalystAction.MAINTAIN:
            continue
        predicted_up = ev.action in (AnalystAction.UPGRADE, AnalystAction.INIT)
        fwd = forward_return_fn(ev)
        correct = (predicted_up and fwd > 0) or (not predicted_up and fwd < 0)
        total[ev.firm] = total.get(ev.firm, 0) + 1
        hits[ev.firm] = hits.get(ev.firm, 0) + (1 if correct else 0)
    return {
        firm: (hits[firm] / total[firm] if total[firm] >= min_calls else 0.5)
        for firm in total
    }


def analyst_conviction_score(
    recent_events: list[AnalystRating],
    firm_scores: dict[str, float],
    now: datetime,
    lookback_days: int = 30,
    half_life_days: float = 14.0,
) -> float:
    """1-10 sub-score from recent rating events, weighted by firm accuracy and
    freshness-decayed. Events outside [now-lookback_days, now] are ignored
    (point-in-time + recency). Unknown firms weighted at the neutral 0.5."""
    if not recent_events:
        return 5.0
    signal = 0.0
    for ev in recent_events:
        age_days = (now - ev.published_at).days
        if age_days < 0 or age_days > lookback_days:
            continue
        weight = firm_scores.get(ev.firm, 0.5)
        decay = 0.5 ** (age_days / half_life_days)
        if ev.action in (AnalystAction.UPGRADE, AnalystAction.INIT):
            direction = 1.0
        elif ev.action == AnalystAction.DOWNGRADE:
            direction = -1.0
        else:
            direction = 0.0
        signal += direction * weight * decay
    return max(1.0, min(10.0, 5.0 + signal * 3.0))
