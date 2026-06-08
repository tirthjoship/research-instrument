def test_brier_score_perfect_is_zero():
    from domain.calibration import brier_score

    assert brier_score([1.0, 0.0, 1.0], [1, 0, 1]) == 0.0


def test_brier_score_worst_is_one():
    from domain.calibration import brier_score

    assert brier_score([0.0, 1.0], [1, 0]) == 1.0


def test_brier_score_empty_is_zero():
    from domain.calibration import brier_score

    assert brier_score([], []) == 0.0


def test_base_rate_from_history_buckets_downtrend_higher_down_rate():
    from domain.calibration import base_rate_from_history

    closes = [float(100 - i) for i in range(0, 60)]
    out = base_rate_from_history(closes, trend_window=10, atr_window=10, horizon=5)
    assert "below" in out
    assert out["below"]["n"] > 0
    assert 0.0 <= out["below"]["down_rate"] <= 1.0
    assert out["below"]["down_rate"] > 0.5
