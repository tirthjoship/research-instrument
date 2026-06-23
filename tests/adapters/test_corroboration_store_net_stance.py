# tests/adapters/test_corroboration_store_net_stance.py
from datetime import date

from adapters.data.corroboration_store import _claims_to_snapshots
from domain.corroboration_models import HarvestedClaim, Stance


def _claim(ticker: str, stance: Stance, verified: bool = True) -> HarvestedClaim:
    return HarvestedClaim(
        source_name="Example",
        ticker=ticker,
        stance=stance,
        thesis_summary="thesis",
        url="https://example.com",
        published_at=date(2026, 6, 23),
        verified=verified,
        reliability_weight=1.0,
    )


def test_net_stance_bullish_majority() -> None:
    claims = [
        _claim("AAPL", Stance.BULLISH),
        _claim("AAPL", Stance.BULLISH),
        _claim("AAPL", Stance.BEARISH),
    ]
    snaps = _claims_to_snapshots(claims, date(2026, 6, 23))
    assert len(snaps) == 1
    assert snaps[0].net_stance == Stance.BULLISH


def test_net_stance_bearish_majority() -> None:
    claims = [
        _claim("MSFT", Stance.BEARISH),
        _claim("MSFT", Stance.BEARISH),
        _claim("MSFT", Stance.BULLISH),
    ]
    snaps = _claims_to_snapshots(claims, date(2026, 6, 23))
    assert snaps[0].net_stance == Stance.BEARISH


def test_net_stance_neutral_on_tie() -> None:
    claims = [
        _claim("TSLA", Stance.BULLISH),
        _claim("TSLA", Stance.BEARISH),
    ]
    snaps = _claims_to_snapshots(claims, date(2026, 6, 23))
    assert snaps[0].net_stance == Stance.NEUTRAL


def test_unverified_claims_excluded_from_net_stance() -> None:
    claims = [
        _claim("NVDA", Stance.BULLISH, verified=True),
        _claim("NVDA", Stance.BEARISH, verified=False),  # excluded
    ]
    snaps = _claims_to_snapshots(claims, date(2026, 6, 23))
    assert snaps[0].net_stance == Stance.BULLISH
