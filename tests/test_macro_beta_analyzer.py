import numpy as np

from adapters.ml.macro_beta_analyzer import RidgeMacroBetaEstimator


def test_recovers_known_betas():
    rng = np.random.default_rng(0)
    n = 400
    spy = rng.normal(0, 0.01, n)
    tlt = rng.normal(0, 0.01, n)
    y = 0.8 * spy - 0.3 * tlt + rng.normal(0, 0.0005, n)
    est = RidgeMacroBetaEstimator(alpha=0.05)
    betas, r2 = est.estimate(list(y), {"SPY": list(spy), "TLT": list(tlt)}, alpha=0.05)
    assert abs(betas["SPY"] - 0.8) < 0.1
    assert abs(betas["TLT"] - (-0.3)) < 0.1
    assert r2 > 0.8


def test_degenerate_constant_y_no_crash():
    est = RidgeMacroBetaEstimator()
    betas, r2 = est.estimate(
        [0.0] * 50, {"SPY": [0.01] * 50, "TLT": [0.0] * 50}, alpha=0.2
    )
    assert set(betas) == {"SPY", "TLT"}
    assert np.isfinite(r2)


def test_too_few_points_returns_zeros():
    est = RidgeMacroBetaEstimator()
    betas, r2 = est.estimate([0.01], {"SPY": [0.01]}, alpha=0.2)
    assert betas == {"SPY": 0.0}
    assert r2 == 0.0
