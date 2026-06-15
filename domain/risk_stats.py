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


def diversification_ratio(weighted_avg_vol: float, portfolio_vol: float) -> float:
    """(Σ wᵢσᵢ) / σ_portfolio. 1.0 = no diversification benefit. Guards div-by-0."""
    if portfolio_vol <= 0.0:
        return 1.0
    return weighted_avg_vol / portfolio_vol


def risk_contributions(
    weights: Sequence[float], marginal: Sequence[float], portfolio_var: float
) -> list[float]:
    """Euler decomposition: RCᵢ = wᵢ·(Σw)ᵢ / (wᵀΣw). `marginal` = (Σw) per asset.
    Returns fractions summing to 1.0 (empty/zero-var → empty list)."""
    if portfolio_var <= 0.0 or not weights:
        return [0.0 for _ in weights]
    return [w * m / portfolio_var for w, m in zip(weights, marginal)]


def vif_from_r2(r2: float) -> float:
    """Variance inflation factor for a factor whose regression-on-others gave r2."""
    if r2 >= 1.0:
        return float("inf")
    return 1.0 / (1.0 - r2)
