"""Numpy-backed risk statistics: covariance eigenvalues (for ENB), bootstrap R²
and beta CIs, downside beta. Returns plain Python so domain/use-case stay numpy-free."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

import numpy as np
from numpy.typing import NDArray
from sklearn.linear_model import Ridge

_Array = NDArray[Any]


class RiskStatsAnalyzer:
    def __init__(self, seed: int = 0, bootstrap_iters: int = 500) -> None:
        self._seed = seed
        self._iters = bootstrap_iters

    def covariance_eigenvalues(self, returns_matrix: _Array) -> list[float]:
        """Eigenvalues (variance of principal portfolios), descending. Rows=days, cols=holdings."""
        if returns_matrix.ndim != 2 or returns_matrix.shape[1] == 0:
            return []
        cov = np.cov(returns_matrix, rowvar=False)
        cov = np.atleast_2d(cov)
        eigs = np.linalg.eigvalsh(cov)
        return [float(e) for e in sorted((max(e, 0.0) for e in eigs), reverse=True)]

    def _fit_ridge(self, y: _Array, X: _Array, alpha: float) -> _Array:
        y = y - y.mean()
        X = X - X.mean(axis=0, keepdims=True)
        eff = alpha * max(float(np.mean(np.var(X, axis=0))), 1e-12)
        model = Ridge(alpha=eff)
        model.fit(X, y)
        return model.coef_  # type: ignore[no-any-return]

    def _r2(self, y: _Array, X: _Array, alpha: float) -> float:
        y0 = y - y.mean()
        ss_tot = float(np.sum(y0**2))
        if ss_tot == 0.0:
            return 0.0
        coef = self._fit_ridge(y, X, alpha)
        pred = (X - X.mean(axis=0, keepdims=True)) @ coef
        resid = y0 - pred
        return max(min(1.0 - float(np.sum(resid**2)) / ss_tot, 1.0), 0.0)

    def bootstrap_r2_ci(
        self,
        y: Sequence[float] | _Array,
        factor_returns: Mapping[str, Sequence[float]],
        alpha: float,
        ci: float = 0.90,
    ) -> tuple[float, float]:
        rng = np.random.default_rng(self._seed)
        y_arr = np.asarray(y, float)
        X = np.column_stack(
            [np.asarray(factor_returns[f], float) for f in factor_returns]
        )
        n = len(y_arr)
        if n < 20:
            return (0.0, 0.0)
        vals = []
        for _ in range(self._iters):
            idx = rng.integers(0, n, n)
            vals.append(self._r2(y_arr[idx], X[idx], alpha))
        lo_q, hi_q = (1 - ci) / 2, 1 - (1 - ci) / 2
        return (float(np.quantile(vals, lo_q)), float(np.quantile(vals, hi_q)))

    def beta_cis(
        self,
        y: Sequence[float],
        factor_returns: Mapping[str, Sequence[float]],
        alpha: float,
        ci: float = 0.90,
    ) -> dict[str, tuple[float, float]]:
        rng = np.random.default_rng(self._seed + 1)
        factors = list(factor_returns)
        y_arr = np.asarray(y, float)
        X = np.column_stack([np.asarray(factor_returns[f], float) for f in factors])
        n = len(y_arr)
        if n < 20:
            return {f: (0.0, 0.0) for f in factors}
        draws = np.empty((self._iters, len(factors)))
        for b in range(self._iters):
            idx = rng.integers(0, n, n)
            draws[b] = self._fit_ridge(y_arr[idx], X[idx], alpha)
        lo_q, hi_q = (1 - ci) / 2, 1 - (1 - ci) / 2
        return {
            f: (
                float(np.quantile(draws[:, j], lo_q)),
                float(np.quantile(draws[:, j], hi_q)),
            )
            for j, f in enumerate(factors)
        }

    def downside_beta(
        self,
        y: Sequence[float],
        spy: Sequence[float],
        eps: float = 1e-9,
    ) -> float:
        y_arr = np.asarray(y, float)
        spy_arr = np.asarray(spy, float)
        mask = spy_arr < 0.0
        if mask.sum() < 10:
            return 0.0
        yd, sd = y_arr[mask], spy_arr[mask]
        var = float(np.var(sd))
        if var <= eps:
            return 0.0
        return float(np.cov(yd, sd, bias=True)[0, 1] / var)

    def principal_loadings(
        self,
        returns_matrix: _Array,
        tickers: list[str],
        k: int = 3,
    ) -> list[list[str]]:
        """For the top-k principal components, the tickers with the largest |loading|.
        Used to label the ENB 'bets'. Returns [] if matrix degenerate."""
        if returns_matrix.ndim != 2 or returns_matrix.shape[1] == 0:
            return []
        cov = np.atleast_2d(np.cov(returns_matrix, rowvar=False))
        vals, vecs = np.linalg.eigh(cov)
        order = list(reversed(range(len(vals))))[:k]
        out: list[list[str]] = []
        for i in order:
            loadings = np.abs(vecs[:, i])
            top = [
                tickers[j] for j in np.argsort(loadings)[::-1][:3] if j < len(tickers)
            ]
            out.append(top)
        return out
