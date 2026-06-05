from datetime import datetime

import pytest

from domain.analyst import AnalystAction, AnalystRating


def test_analyst_action_members():
    assert AnalystAction("upgrade") is AnalystAction.UPGRADE
    assert {a.value for a in AnalystAction} == {
        "upgrade",
        "downgrade",
        "init",
        "maintain",
    }


def test_analyst_rating_constructs():
    r = AnalystRating(
        ticker="NVDA",
        firm="Goldman Sachs",
        rating="Buy",
        prior_rating="Hold",
        action=AnalystAction.UPGRADE,
        price_target=1200.0,
        published_at=datetime(2026, 6, 1),
        source="finnhub",
    )
    assert r.ticker == "NVDA"
    assert r.action is AnalystAction.UPGRADE
    assert r.prior_rating == "Hold"


def test_negative_price_target_raises():
    with pytest.raises(ValueError):
        AnalystRating(
            ticker="NVDA",
            firm="GS",
            rating="Buy",
            prior_rating=None,
            action=AnalystAction.INIT,
            price_target=-5.0,
            published_at=datetime(2026, 6, 1),
            source="finnhub",
        )


def test_none_price_target_ok():
    r = AnalystRating(
        ticker="NVDA",
        firm="GS",
        rating="Buy",
        prior_rating=None,
        action=AnalystAction.MAINTAIN,
        price_target=None,
        published_at=datetime(2026, 6, 1),
        source="finnhub",
    )
    assert r.price_target is None
