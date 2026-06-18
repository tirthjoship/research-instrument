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


# ---------------------------------------------------------------------------
# Hardening: length-consistency guards — abstain to safe zero-values
# ---------------------------------------------------------------------------


def test_bootstrap_r2_ci_mismatched_lengths_abstains():
    """If any factor series is shorter than y, return (0.0, 0.0) rather than crash."""
    rng = np.random.default_rng(10)
    y = rng.normal(size=250)
    factor_returns = {"SPY": rng.normal(size=200)}  # length mismatch
    a = RiskStatsAnalyzer(seed=10, bootstrap_iters=200)
    result = a.bootstrap_r2_ci(y, factor_returns, alpha=0.2)
    assert result == (0.0, 0.0)


def test_beta_cis_mismatched_lengths_abstains():
    """If any factor series has a different length than y, all CIs → (0.0, 0.0)."""
    rng = np.random.default_rng(11)
    y = rng.normal(size=250)
    factor_returns = {
        "SPY": rng.normal(size=250),
        "QQQ": rng.normal(size=200),  # length mismatch
    }
    a = RiskStatsAnalyzer(seed=11, bootstrap_iters=200)
    result = a.beta_cis(y, factor_returns, alpha=0.2)
    assert result == {"SPY": (0.0, 0.0), "QQQ": (0.0, 0.0)}


def test_downside_beta_mismatched_lengths_abstains():
    """If len(y) != len(spy), return 0.0 rather than crash."""
    rng = np.random.default_rng(12)
    y = rng.normal(size=300)
    spy = rng.normal(size=250)  # length mismatch
    a = RiskStatsAnalyzer(seed=12)
    result = a.downside_beta(y.tolist(), spy.tolist())
    assert result == 0.0


def test_principal_loadings_ticker_mismatch_returns_empty():
    """3-col matrix but only 2 tickers → can't label PCs → return []."""
    rng = np.random.default_rng(13)
    X = rng.normal(size=(250, 3))
    a = RiskStatsAnalyzer(seed=13)
    result = a.principal_loadings(X, ["A", "B"], k=2)
    assert result == []


# ---------------------------------------------------------------------------
# Locks for named-constant branches
# ---------------------------------------------------------------------------


def test_bootstrap_r2_ci_too_few_points_abstains():
    """n < _MIN_POINTS (20) → abstain to (0.0, 0.0)."""
    rng = np.random.default_rng(14)
    y = rng.normal(size=10)
    factor_returns = {"SPY": rng.normal(size=10)}
    a = RiskStatsAnalyzer(seed=14, bootstrap_iters=200)
    result = a.bootstrap_r2_ci(y, factor_returns, alpha=0.2)
    assert result == (0.0, 0.0)


def test_downside_beta_no_down_days_abstains():
    """spy all positive → no down days → mask.sum() < _MIN_DOWN_DAYS → return 0.0."""
    rng = np.random.default_rng(15)
    spy = np.abs(rng.normal(size=300))  # all positive, no down days
    y = rng.normal(size=300)
    a = RiskStatsAnalyzer(seed=15)
    result = a.downside_beta(y.tolist(), spy.tolist())
    assert result == 0.0


# ---------------------------------------------------------------------------
# Task 8a: new methods
# ---------------------------------------------------------------------------


def test_risk_contribution_terms_sum_to_var():
    rng = np.random.default_rng(7)
    X = rng.normal(size=(300, 3))
    a = RiskStatsAnalyzer(seed=7)
    w = [0.5, 0.3, 0.2]
    marginal, port_var = a.risk_contribution_terms(X.tolist(), w)
    assert len(marginal) == 3 and port_var > 0
    # Σ w_i * marginal_i == port_var (Euler identity)
    assert abs(sum(wi * mi for wi, mi in zip(w, marginal)) - port_var) < 1e-9


def test_risk_contribution_terms_length_mismatch():
    a = RiskStatsAnalyzer(seed=7)
    assert a.risk_contribution_terms([[0.1, 0.2]], [0.5]) == ([], 0.0)


def test_factor_vif_r2_collinear_high():
    rng = np.random.default_rng(8)
    base = rng.normal(size=300)
    F = {
        "A": base.tolist(),
        "B": (base + 0.001 * rng.normal(size=300)).tolist(),
        "C": rng.normal(size=300).tolist(),
    }
    a = RiskStatsAnalyzer(seed=8)
    r2 = a.factor_vif_r2(F)
    assert r2["A"] > 0.95  # A explained by B (collinear)
    assert r2["C"] < 0.5  # C independent


def test_factor_vif_r2_single_factor_zero():
    a = RiskStatsAnalyzer(seed=8)
    assert a.factor_vif_r2({"SPY": [0.1, 0.2, 0.3]}) == {"SPY": 0.0}


def test_covariance_eigenvalues_accepts_plain_list():
    a = RiskStatsAnalyzer(seed=0)
    eigs = a.covariance_eigenvalues(
        [[0.1, 0.2], [0.2, 0.1], [0.15, 0.18], [0.05, 0.22]]
    )
    assert eigs and list(eigs) == sorted(eigs, reverse=True)
