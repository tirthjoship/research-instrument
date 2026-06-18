import math

import pytest
from hypothesis import given
from hypothesis import strategies as st

from domain.risk_stats import (
    adjusted_r2,
    diversification_ratio,
    effective_number_of_bets,
    risk_contributions,
    vif_from_r2,
)


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


def test_diversification_ratio_uncorrelated_gt_one():
    dr = diversification_ratio(weighted_avg_vol=1.0, portfolio_vol=1.0 / math.sqrt(2))
    assert dr == pytest.approx(math.sqrt(2), rel=1e-9)


def test_diversification_ratio_zero_portfolio_vol_is_one():
    assert diversification_ratio(1.0, 0.0) == 1.0


def test_risk_contributions_sum_to_one():
    rc = risk_contributions(weights=[0.5, 0.5], marginal=[0.5, 0.5], portfolio_var=0.5)
    assert sum(rc.values()) if isinstance(rc, dict) else sum(rc) == pytest.approx(1.0)


def test_vif_from_r2():
    assert vif_from_r2(0.8) == pytest.approx(1 / (1 - 0.8))
    assert vif_from_r2(1.0) == float("inf")


@given(st.lists(st.floats(min_value=0.0, max_value=10.0), min_size=1, max_size=12))
def test_enb_within_one_and_n(eigs):
    total = sum(eigs)
    enb = effective_number_of_bets(eigs)
    if total > 0:
        assert 0.999 <= enb <= len([e for e in eigs if e > 0]) + 1e-6
