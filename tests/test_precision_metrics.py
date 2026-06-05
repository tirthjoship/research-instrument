from application.precision_metrics import (
    expected_profit_per_signal,
    f_beta,
    monotonic_precision_curve,
    precision_at_decile,
)


def test_precision_at_decile_perfect_ranking():
    scores = [9, 8, 7, 6, 5, 4, 3, 2, 1, 0]
    wins = [1, 1, 1, 1, 1, 0, 0, 0, 0, 0]
    assert precision_at_decile(scores, wins, decile=0.1) == 1.0


def test_precision_at_decile_random_is_base_rate():
    scores = list(range(20))
    wins = [1, 0] * 10
    p = precision_at_decile(scores, wins, decile=0.5)
    assert 0.3 <= p <= 0.7


def test_monotonic_curve_detects_monotonic():
    scores = list(range(100))
    wins = [1 if s >= 50 else 0 for s in scores]
    curve = monotonic_precision_curve(scores, wins, n_bins=5)
    assert curve == sorted(curve)
    assert len(curve) == 5


def test_f_beta_half_weights_precision():
    assert f_beta(precision=1.0, recall=0.5, beta=0.5) > f_beta(1.0, 0.5, 1.0)


def test_expected_profit_positive_when_precision_high():
    ep = expected_profit_per_signal(
        precision=0.7, avg_win=0.06, avg_loss=0.04, cost=0.001
    )
    assert ep > 0
    ep2 = expected_profit_per_signal(
        precision=0.4, avg_win=0.05, avg_loss=0.05, cost=0.002
    )
    assert ep2 < 0
