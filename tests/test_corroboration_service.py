# tests/test_corroboration_service.py
from datetime import date

from hypothesis import given
from hypothesis import strategies as st

from domain.corroboration_models import (
    ConvergenceTier,
    HarvestedClaim,
    OurReadout,
    Stance,
    TrendHealth,
)
from domain.corroboration_service import CorroborationService


def _claim(src, stance, w, ticker="NVDA"):
    return HarvestedClaim(
        src, ticker, stance, "why", "https://u", date(2026, 6, 18), True, w
    )


def _readout(pct=5.0, trend=TrendHealth.HEALTHY, div=False, disc=None):
    return OurReadout(pct, trend, div, disc)


def test_three_bull_sources_plus_our_agreement_is_strong():
    svc = CorroborationService()
    claims = [
        _claim("A", Stance.BULLISH, 0.8),
        _claim("B", Stance.BULLISH, 0.7),
        _claim("C", Stance.BULLISH, 0.6),
    ]
    cand = svc.corroborate(
        "NVDA", date(2026, 6, 20), claims, _readout(pct=5.0), held=True
    )
    assert cand.agreement.weighted_score > 0.9
    assert cand.agreement.our_alignment == "AGREES"
    assert cand.convergence is ConvergenceTier.STRONG


def test_diverges_yields_conflicted_even_when_sources_strong():
    svc = CorroborationService()
    claims = [
        _claim("A", Stance.BULLISH, 0.9),
        _claim("B", Stance.BULLISH, 0.9),
        _claim("C", Stance.BULLISH, 0.9),
    ]
    cand = svc.corroborate(
        "NVDA",
        date(2026, 6, 20),
        claims,
        _readout(trend=TrendHealth.BROKEN),
        held=False,
    )
    assert cand.convergence is ConvergenceTier.CONFLICTED


def test_no_verified_sources_is_none():
    svc = CorroborationService()
    unverified = HarvestedClaim(
        "A", "NVDA", Stance.BULLISH, "w", "https://u", date(2026, 6, 18), False, 0.5
    )
    cand = svc.corroborate(
        "NVDA", date(2026, 6, 20), [unverified], _readout(), held=False
    )
    assert cand.convergence is ConvergenceTier.NONE
    assert cand.verification == "NONE_DROPPED"


def test_conflicting_sources_near_zero_is_conflicted():
    svc = CorroborationService()
    claims = [_claim("A", Stance.BULLISH, 0.5), _claim("B", Stance.BEARISH, 0.5)]
    cand = svc.corroborate("NVDA", date(2026, 6, 20), claims, _readout(), held=False)
    assert cand.convergence is ConvergenceTier.CONFLICTED


@given(w=st.floats(min_value=0.01, max_value=1.0))
def test_all_bearish_never_strong_bull(w):
    svc = CorroborationService()
    claims = [
        _claim("A", Stance.BEARISH, w),
        _claim("B", Stance.BEARISH, w),
        _claim("C", Stance.BEARISH, w),
    ]
    cand = svc.corroborate(
        "NVDA",
        date(2026, 6, 20),
        claims,
        _readout(trend=TrendHealth.HEALTHY),
        held=False,
    )
    assert cand.agreement.weighted_score < 0
