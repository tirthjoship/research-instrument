"""Pure descriptive-risk statistics (stdlib + math only). NO numpy, NO prediction.

Every function is deterministic arithmetic so it is fully unit/property-testable.
Heavy linear algebra (covariance, PCA, bootstrap) lives in the adapter
adapters/ml/risk_stats_analyzer.py; this module takes its scalar/vector outputs.
"""

from __future__ import annotations


def adjusted_r2(r2: float, n: int, p: int) -> float:
    """Adjusted R²: penalizes the p factors. Returns raw r2 if not adjustable."""
    denom = n - p - 1
    if denom <= 0:
        return r2
    if r2 == 0.0:
        return 0.0
    return 1.0 - (1.0 - r2) * (n - 1) / denom
