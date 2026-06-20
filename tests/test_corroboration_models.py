# tests/test_corroboration_models.py
from datetime import date

from domain.corroboration_models import HarvestedClaim, Stance


def test_harvested_claim_is_frozen_and_carries_attribution():
    claim = HarvestedClaim(
        source_name="Morningstar",
        ticker="NVDA",
        stance=Stance.BULLISH,
        thesis_summary="5-star, AI demand durable",
        url="https://x/y",
        published_at=date(2026, 6, 18),
        verified=True,
        reliability_weight=0.7,
    )
    assert claim.stance is Stance.BULLISH
    assert claim.verified is True
    assert 0.0 <= claim.reliability_weight <= 1.0
