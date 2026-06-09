"""Ridge factor-beta estimator (macro-beta scrubber, Unit A, ADR-052).

Fits sklearn Ridge on RAW de-meaned daily returns with NO StandardScaler, so
`.coef_` are raw, dollar-interpretable betas. This is deliberately NOT a reuse
of RidgePredictor (which wraps a StandardScaler and never exposes coefficients).
"""

from __future__ import annotations

import numpy as np
from sklearn.linear_model import Ridge

_MIN_POINTS = 20  # below this, betas are noise — abstain to zeros.


class RidgeMacroBetaEstimator:
    """Implements MacroBetaEstimatorPort."""

    def __init__(self, alpha: float = 0.2) -> None:
        self._alpha = alpha

    def estimate(
        self,
        y_returns: list[float],
        factor_returns: dict[str, list[float]],
        alpha: float | None = None,
    ) -> tuple[dict[str, float], float]:
        factors = list(factor_returns)
        zeros = {f: 0.0 for f in factors}
        n = len(y_returns)
        if n < _MIN_POINTS or not factors:
            return zeros, 0.0
        if any(len(factor_returns[f]) != n for f in factors):
            return zeros, 0.0

        y = np.asarray(y_returns, dtype=float)
        x = np.column_stack(
            [np.asarray(factor_returns[f], dtype=float) for f in factors]
        )
        y = y - y.mean()
        x = x - x.mean(axis=0, keepdims=True)

        # Scale alpha by mean feature variance so the caller's alpha is a
        # relative penalty fraction (0–1), not an absolute raw-return penalty.
        # Without this, alpha=0.05 >> XtX diagonal (~0.04 for daily returns
        # with std ~1%), causing catastrophic shrinkage.
        mean_feature_var = float(np.mean(np.var(x, axis=0)))
        effective_alpha = (alpha if alpha is not None else self._alpha) * max(
            mean_feature_var, 1e-12
        )

        model = Ridge(alpha=effective_alpha)
        model.fit(x, y)
        betas = {f: float(c) for f, c in zip(factors, model.coef_)}

        ss_tot = float(np.sum(y**2))
        if ss_tot == 0.0:
            return betas, 0.0
        resid = y - model.predict(x)
        r2 = 1.0 - float(np.sum(resid**2)) / ss_tot
        return betas, max(min(r2, 1.0), 0.0)
