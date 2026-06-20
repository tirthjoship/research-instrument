# tests/test_corroboration_directional.py
from datetime import date

from domain.corroboration_models import HarvestedClaim, OurReadout, Stance, TrendHealth
from domain.corroboration_service import CorroborationService


def _cand(svc, ticker, stance):
    c = HarvestedClaim(
        "A", ticker, stance, "w", "https://u", date(2026, 6, 18), True, 0.8
    )
    return svc.corroborate(
        ticker,
        date(2026, 6, 20),
        [c, c, c],
        OurReadout(5.0, TrendHealth.HEALTHY, False, None),
        held=False,
    )


def test_rollup_groups_by_theme_and_flags_underexposed_lean_in():
    svc = CorroborationService()
    cands = [_cand(svc, "NVDA", Stance.BULLISH), _cand(svc, "AMD", Stance.BULLISH)]
    themes = {"ai_infra": ["NVDA", "AMD"]}
    exposure = {"ai_infra": 2.0}  # only 2% of book in a strongly-corroborated theme
    views = svc.roll_up(cands, themes, exposure)
    ai = next(v for v in views if v.group_name == "ai_infra")
    assert ai.net_stance is Stance.BULLISH
    assert ai.tilt == "LEAN_IN"
