"""Pure descriptive-risk statistics (stdlib + math only). NO numpy, NO prediction.

Every function is deterministic arithmetic so it is fully unit/property-testable.
Heavy linear algebra (covariance, PCA, bootstrap) lives in the adapter
adapters/ml/risk_stats_analyzer.py; this module takes its scalar/vector outputs.
"""

from __future__ import annotations

import math
from collections.abc import Sequence


def adjusted_r2(r2: float, n: int, p: int) -> float:
    """Adjusted R²: penalizes the p factors. Returns raw r2 if not adjustable."""
    denom = n - p - 1
    if denom <= 0:
        return r2
    if r2 == 0.0:
        return 0.0
    return 1.0 - (1.0 - r2) * (n - 1) / denom


def effective_number_of_bets(eigenvalues: Sequence[float]) -> float:
    """Meucci ENB = exp(-Σ pᵢ ln pᵢ) over variance fractions pᵢ (eigenvalues
    of the holdings covariance, i.e. variance of the principal portfolios)."""
    vals = [max(v, 0.0) for v in eigenvalues]
    total = sum(vals)
    if total <= 0.0:
        return 0.0
    entropy = 0.0
    for v in vals:
        p = v / total
        if p > 0.0:
            entropy -= p * math.log(p)
    return math.exp(entropy)
