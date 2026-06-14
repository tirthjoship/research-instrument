from hypothesis import given
from hypothesis import strategies as st

from domain.risk_rubric import (
    NetBetaBand,
    ShareBand,
    classify_net_beta,
    classify_systematic_share,
    net_beta_position,
)


def test_net_beta_bands():
    assert classify_net_beta(-0.3) is NetBetaBand.HEDGED
    assert classify_net_beta(0.5) is NetBetaBand.DEFENSIVE
    assert classify_net_beta(1.0) is NetBetaBand.MARKET_LIKE
    assert classify_net_beta(1.42) is NetBetaBand.ELEVATED
    assert classify_net_beta(1.8) is NetBetaBand.AGGRESSIVE


def test_net_beta_boundaries_lower_inclusive_upper_exclusive():
    assert classify_net_beta(0.8) is NetBetaBand.MARKET_LIKE
    assert classify_net_beta(1.2) is NetBetaBand.ELEVATED
    assert classify_net_beta(1.6) is NetBetaBand.AGGRESSIVE
    assert classify_net_beta(0.0) is NetBetaBand.DEFENSIVE


def test_systematic_share_bands_and_flag_boundary():
    assert classify_systematic_share(0.30, flag=0.60) is ShareBand.STOCK_SPECIFIC
    assert classify_systematic_share(0.50, flag=0.60) is ShareBand.BALANCED
    assert classify_systematic_share(0.60, flag=0.60) is ShareBand.MACRO_LEANING
    assert classify_systematic_share(0.80, flag=0.60) is ShareBand.MACRO_DOMINATED


def test_net_beta_position_maps_domain_minus_half_to_two():
    assert net_beta_position(0.0) == 20.0
    assert net_beta_position(1.0) == 60.0
    assert abs(net_beta_position(1.6) - 84.0) < 1e-9
    assert net_beta_position(-1.0) == 0.0
    assert net_beta_position(3.0) == 100.0


@given(st.floats(min_value=-1, max_value=3, allow_nan=False))
def test_net_beta_position_monotonic_nondecreasing(v):
    assert net_beta_position(v - 0.01) <= net_beta_position(v) + 1e-9
