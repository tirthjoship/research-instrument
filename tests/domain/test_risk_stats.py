import pytest

from domain.risk_stats import adjusted_r2, effective_number_of_bets


def test_adjusted_r2_penalizes_parameters():
    adj = adjusted_r2(0.71, n=252, p=9)
    assert adj < 0.71
    assert adj == pytest.approx(1 - (1 - 0.71) * (252 - 1) / (252 - 9 - 1), rel=1e-9)


def test_adjusted_r2_degenerate_guards():
    assert adjusted_r2(0.5, n=5, p=9) == 0.5
    assert adjusted_r2(0.0, n=100, p=3) == 0.0


def test_enb_equal_uncorrelated_equals_n():
    assert effective_number_of_bets([1.0, 1.0, 1.0, 1.0]) == pytest.approx(4.0)


def test_enb_one_dominant_equals_one():
    assert effective_number_of_bets([1.0, 0.0, 0.0]) == pytest.approx(1.0)


def test_enb_between_one_and_n():
    enb = effective_number_of_bets([0.64, 0.14, 0.09, 0.05, 0.04, 0.04])
    assert 1.0 < enb < 6.0


def test_enb_empty_or_zero_is_zero():
    assert effective_number_of_bets([]) == 0.0
    assert effective_number_of_bets([0.0, 0.0]) == 0.0
