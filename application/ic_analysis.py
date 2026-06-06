"""Cross-sectional Information Coefficient (rank-IC) analysis.

IC = Spearman rank correlation between a signal and forward returns, computed
ACROSS names on a single date, then aggregated over dates. The standard quant
measure of monotonic predictive power; robust to a few outlier names.
"""

from __future__ import annotations

import math
from typing import Any


def _rank(xs: list[float]) -> list[float]:
    order = sorted(range(len(xs)), key=lambda i: xs[i])
    ranks = [0.0] * len(xs)
    i = 0
    while i < len(xs):
        j = i
        while j + 1 < len(xs) and xs[order[j + 1]] == xs[order[i]]:
            j += 1
        avg = (i + j) / 2.0 + 1.0  # average rank for ties (1-based)
        for k in range(i, j + 1):
            ranks[order[k]] = avg
        i = j + 1
    return ranks


def _pearson(a: list[float], b: list[float]) -> float:
    n = len(a)
    ma = sum(a) / n
    mb = sum(b) / n
    cov = sum((a[i] - ma) * (b[i] - mb) for i in range(n))
    va = math.sqrt(sum((x - ma) ** 2 for x in a))
    vb = math.sqrt(sum((x - mb) ** 2 for x in b))
    if va == 0.0 or vb == 0.0:
        return float("nan")
    return cov / (va * vb)


def spearman_ic(signal: list[float], forward_return: list[float]) -> float:
    """Spearman rank-IC for one date. NaN if < 2 points or degenerate."""
    if len(signal) != len(forward_return) or len(signal) < 2:
        return float("nan")
    return _pearson(_rank(signal), _rank(forward_return))


def aggregate_ic(
    per_date: list[tuple[list[float], list[float]]], min_names: int = 50
) -> dict[str, Any]:
    """Aggregate per-date (signal, forward_return) pairs into IC summary.

    Skips dates with fewer than min_names valid names. Returns mean IC,
    IC IR (mean/std), % positive dates, and the per-date IC series (for the
    bootstrap / date-level significance step).
    """
    ic_series: list[float] = []
    for signal, fwd in per_date:
        if len(signal) < min_names:
            continue
        ic = spearman_ic(signal, fwd)
        if not math.isnan(ic):
            ic_series.append(round(ic, 15))
    n = len(ic_series)
    if n == 0:
        return {
            "n_dates": 0,
            "mean_ic": 0.0,
            "ic_ir": 0.0,
            "pct_positive_dates": 0.0,
            "ic_series": [],
        }
    mean_ic = sum(ic_series) / n
    if n > 1:
        var = sum((x - mean_ic) ** 2 for x in ic_series) / (n - 1)
        std = math.sqrt(var)
    else:
        std = 0.0
    return {
        "n_dates": n,
        "mean_ic": mean_ic,
        "ic_ir": (mean_ic / std) if std > 0 else 0.0,
        "pct_positive_dates": sum(1 for x in ic_series if x > 0) / n,
        "ic_series": ic_series,
    }
