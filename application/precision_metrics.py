"""Precision-first evaluation metrics. Pure functions, no I/O."""

from __future__ import annotations


def _rank_desc(scores: list[float], wins: list[int]) -> list[int]:
    order = sorted(range(len(scores)), key=lambda i: scores[i], reverse=True)
    return [wins[i] for i in order]


def precision_at_decile(
    scores: list[float], wins: list[int], decile: float = 0.1
) -> float:
    """Fraction of the top `decile` (by score) that won. decile in (0,1]."""
    if not scores:
        return 0.0
    ranked = _rank_desc(scores, wins)
    k = max(1, round(len(ranked) * decile))
    top = ranked[:k]
    return sum(top) / len(top)


def monotonic_precision_curve(
    scores: list[float], wins: list[int], n_bins: int = 10
) -> list[float]:
    """Precision per score-bin, lowest-score bin -> highest. Healthy conviction => non-decreasing."""
    if not scores:
        return [0.0] * n_bins
    order = sorted(range(len(scores)), key=lambda i: scores[i])
    binned = [wins[i] for i in order]
    out: list[float] = []
    size = max(1, len(binned) // n_bins)
    for b in range(n_bins):
        chunk = (
            binned[b * size : (b + 1) * size] if b < n_bins - 1 else binned[b * size :]
        )
        out.append(sum(chunk) / len(chunk) if chunk else 0.0)
    return out


def f_beta(precision: float, recall: float, beta: float = 0.5) -> float:
    """F-beta. beta<1 weights precision over recall."""
    b2 = beta * beta
    denom = b2 * precision + recall
    if denom == 0:
        return 0.0
    return (1 + b2) * precision * recall / denom


def expected_profit_per_signal(
    precision: float, avg_win: float, avg_loss: float, cost: float
) -> float:
    """E[profit] = P(win)*avg_win - P(loss)*avg_loss - cost. The real-money gate."""
    return precision * avg_win - (1 - precision) * avg_loss - cost
