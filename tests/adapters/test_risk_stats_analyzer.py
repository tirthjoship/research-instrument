import numpy as np
import pytest

from adapters.ml.risk_stats_analyzer import RiskStatsAnalyzer


def _series(rng, n, k):
    return rng.normal(size=(n, k))


def test_eigenvalues_descending_and_positive():
    rng = np.random.default_rng(0)
    X = _series(rng, 250, 5)
    a = RiskStatsAnalyzer(seed=0)
    eigs = a.covariance_eigenvalues(X)
    assert list(eigs) == sorted(eigs, reverse=True)
    assert all(e >= -1e-9 for e in eigs)


def test_bootstrap_ci_brackets_point_estimate():
    rng = np.random.default_rng(1)
    y = rng.normal(size=250)
    F = {"SPY": rng.normal(size=250)}
    a = RiskStatsAnalyzer(seed=1, bootstrap_iters=200)
    lo, hi = a.bootstrap_r2_ci(y, F, alpha=0.2)
    assert 0.0 <= lo <= hi <= 1.0


def test_downside_beta_uses_only_down_days():
    rng = np.random.default_rng(2)
    spy = rng.normal(size=300)
    y = 1.3 * spy + 0.0 * rng.normal(size=300)
    a = RiskStatsAnalyzer(seed=2)
    db = a.downside_beta(y.tolist(), spy.tolist())
    assert db == pytest.approx(1.3, abs=0.15)


def test_beta_ci_straddle_zero_flagged():
    rng = np.random.default_rng(3)
    spy = rng.normal(size=300)
    noise = rng.normal(size=300)
    y = 1.0 * spy
    a = RiskStatsAnalyzer(seed=3, bootstrap_iters=200)
    cis = a.beta_cis(
        y.tolist(), {"SPY": spy.tolist(), "NOISE": noise.tolist()}, alpha=0.2
    )
    lo, hi = cis["NOISE"]
    assert lo < 0 < hi


def test_principal_loadings_returns_top_tickers():
    rng = np.random.default_rng(4)
    base = rng.normal(size=(250, 1))
    X = np.hstack([base + 0.01 * rng.normal(size=(250, 1)) for _ in range(3)])
    a = RiskStatsAnalyzer(seed=4)
    loads = a.principal_loadings(X, ["A", "B", "C"], k=2)
    assert loads and set(loads[0]).issubset({"A", "B", "C"})
