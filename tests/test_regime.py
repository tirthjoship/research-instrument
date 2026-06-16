from hypothesis import given
from hypothesis import strategies as st

from domain.factor_scores import FACTOR_KEYS
from domain.regime import Regime, classify_regime, screen_tilt


def test_clear_uptrend_low_vix_is_risk_on() -> None:
    assert classify_regime(spy_trend_health=1.2, vix_level=14.0) == Regime.RISK_ON


def test_broken_trend_is_risk_off() -> None:
    assert classify_regime(spy_trend_health=-0.8, vix_level=15.0) == Regime.RISK_OFF


def test_high_vix_is_risk_off_even_if_trend_ok() -> None:
    assert classify_regime(spy_trend_health=0.7, vix_level=30.0) == Regime.RISK_OFF


def test_middle_is_neutral() -> None:
    assert classify_regime(spy_trend_health=0.2, vix_level=20.0) == Regime.NEUTRAL


@given(t1=st.floats(-3, 3), t2=st.floats(-3, 3), vix=st.floats(8, 40))
def test_monotone_in_trend(t1: float, t2: float, vix: float) -> None:
    order = {Regime.RISK_OFF: 0, Regime.NEUTRAL: 1, Regime.RISK_ON: 2}
    lo, hi = (t1, t2) if t1 <= t2 else (t2, t1)
    assert order[classify_regime(lo, vix)] <= order[classify_regime(hi, vix)]


@given(trend=st.floats(-3, 3), v1=st.floats(8, 40), v2=st.floats(8, 40))
def test_monotone_in_vix(trend: float, v1: float, v2: float) -> None:
    order = {Regime.RISK_OFF: 0, Regime.NEUTRAL: 1, Regime.RISK_ON: 2}
    lo, hi = (v1, v2) if v1 <= v2 else (v2, v1)
    assert order[classify_regime(trend, hi)] <= order[classify_regime(trend, lo)]


def test_tilt_weights_sum_to_one_each_regime() -> None:
    for regime in Regime:
        w = screen_tilt(regime)
        assert set(w.keys()) == set(FACTOR_KEYS)
        assert abs(sum(w.values()) - 1.0) < 1e-9


def test_risk_off_favors_quality_over_momentum() -> None:
    w = screen_tilt(Regime.RISK_OFF)
    assert w["quality"] > w["momentum"]


def test_risk_on_favors_momentum_over_quality() -> None:
    w = screen_tilt(Regime.RISK_ON)
    assert w["momentum"] > w["quality"]


def test_neutral_is_equal_weight() -> None:
    # NEUTRAL is equal-weight across all 5 FACTOR_KEYS → 1/5 = 0.20 each
    w = screen_tilt(Regime.NEUTRAL)
    expected = 1.0 / len(FACTOR_KEYS)
    assert all(abs(v - expected) < 1e-9 for v in w.values())
