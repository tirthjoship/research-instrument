"""Numpy-backed risk statistics: covariance eigenvalues (for ENB), bootstrap R²
and beta CIs, downside beta. Returns plain Python so domain/use-case stay numpy-free."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

import numpy as np
from numpy.typing import NDArray
from sklearn.linear_model import Ridge

_Array = NDArray[Any]

# Named thresholds — mirror macro_beta_analyzer._MIN_POINTS convention.
_MIN_POINTS = 20  # below this, bootstrap results are noise; abstain to zeros
_MIN_DOWN_DAYS = 10  # minimum negative-SPY days needed for a stable downside beta


class RiskStatsAnalyzer:
    def __init__(self, seed: int = 0, bootstrap_iters: int = 500) -> None:
        self._seed = seed
        self._iters = bootstrap_iters

    def covariance_eigenvalues(
        self, returns_matrix: Sequence[Sequence[float]] | _Array
    ) -> list[float]:
        """Eigenvalues (variance of principal portfolios), descending. Rows=days, cols=holdings."""
        m = np.asarray(returns_matrix, dtype=float)
        if m.ndim != 2 or m.shape[1] == 0:
            return []
        cov = np.cov(m, rowvar=False)
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
        n = len(y_arr)
        if any(len(factor_returns[f]) != n for f in factor_returns):
            return (0.0, 0.0)
        X = np.column_stack(
            [np.asarray(factor_returns[f], float) for f in factor_returns]
        )
        if n < _MIN_POINTS:
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
        n = len(y_arr)
        if any(len(factor_returns[f]) != n for f in factors):
            return {f: (0.0, 0.0) for f in factors}
        X = np.column_stack([np.asarray(factor_returns[f], float) for f in factors])
        if n < _MIN_POINTS:
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
        if len(y_arr) != len(spy_arr):
            return 0.0
        mask = spy_arr < 0.0
        if mask.sum() < _MIN_DOWN_DAYS:
            return 0.0
        yd, sd = y_arr[mask], spy_arr[mask]
        var = float(np.var(sd))
        if var <= eps:
            return 0.0
        return float(np.cov(yd, sd, bias=True)[0, 1] / var)

    def principal_loadings(
        self,
        returns_matrix: Sequence[Sequence[float]] | _Array,
        tickers: list[str],
        k: int = 3,
    ) -> list[list[str]]:
        """For the top-k principal components, the tickers with the largest |loading|.
        Used to label the ENB 'bets'. Returns [] if matrix degenerate.

        Uses eigenvectors only (eigenvalue sign is irrelevant for |loading| ranking),
        unlike covariance_eigenvalues which clamps eigenvalues to remove numerical noise.
        """
        m = np.asarray(returns_matrix, dtype=float)
        if m.ndim != 2 or m.shape[1] == 0:
            return []
        if m.shape[1] != len(tickers):
            return []
        cov = np.atleast_2d(np.cov(m, rowvar=False))
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

    def risk_contribution_terms(
        self,
        returns_matrix: Sequence[Sequence[float]] | _Array,
        weights: Sequence[float],
    ) -> tuple[list[float], float]:
        """Euler risk-decomposition terms from the holdings covariance.

        Returns (marginal, portfolio_var) where marginal[i] = (Σ w)_i and
        portfolio_var = wᵀ Σ w. Degenerate matrix / length mismatch → ([], 0.0).
        """
        m = np.asarray(returns_matrix, dtype=float)
        if m.ndim != 2 or m.shape[1] == 0 or m.shape[1] != len(weights):
            return ([], 0.0)
        cov = np.atleast_2d(np.cov(m, rowvar=False))
        w = np.asarray(weights, dtype=float)
        sigma_w = cov @ w
        port_var = float(w @ cov @ w)
        return ([float(x) for x in sigma_w], port_var)

    def factor_vif_r2(
        self, factor_returns: Mapping[str, Sequence[float]]
    ) -> dict[str, float]:
        """Per-factor R² from regressing that factor on all OTHER factors (OLS,
        de-meaned, via least squares). Feeds domain vif_from_r2. <2 factors → {f: 0.0}.
        """
        factors = list(factor_returns)
        if len(factors) < 2:
            return {f: 0.0 for f in factors}
        arrays = [np.asarray(factor_returns[f], dtype=float) for f in factors]
        n = len(arrays[0])
        # Guard length mismatch across factor series
        if any(len(a) != n for a in arrays):
            return {f: 0.0 for f in factors}
        # De-mean each factor
        demeaned = [a - a.mean() for a in arrays]
        result: dict[str, float] = {}
        for j, target in enumerate(factors):
            y = demeaned[j]
            # Build X from all OTHER factors
            other_cols = [demeaned[i] for i in range(len(factors)) if i != j]
            X = np.column_stack(other_cols)
            coef, *_ = np.linalg.lstsq(X, y, rcond=None)
            pred = X @ coef
            ss_tot = float(np.sum(y**2))
            r2 = (
                0.0
                if ss_tot == 0
                else max(min(1.0 - float(np.sum((y - pred) ** 2)) / ss_tot, 1.0), 0.0)
            )
            result[target] = r2
        return result
