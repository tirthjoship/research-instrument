from datetime import datetime

from adapters.data.finnhub_analyst_adapter import parse_upgrade_downgrade
from domain.analyst import AnalystAction, AnalystRating
from tests.fakes.fake_analyst_source import FakeAnalystSource


def test_parse_maps_and_filters_point_in_time():
    payload = [
        {
            "symbol": "NVDA",
            "gradeTime": int(datetime(2026, 6, 1).timestamp()),
            "company": "Goldman Sachs",
            "fromGrade": "Hold",
            "toGrade": "Buy",
            "action": "up",
        },
        {
            "symbol": "NVDA",
            "gradeTime": int(datetime(2027, 1, 1).timestamp()),
            "company": "Future Co",
            "fromGrade": "",
            "toGrade": "Buy",
            "action": "up",
        },
    ]
    out = parse_upgrade_downgrade(
        payload, since=datetime(2026, 1, 1), until=datetime(2026, 12, 31)
    )
    assert len(out) == 1
    r = out[0]
    assert r.firm == "Goldman Sachs"
    assert r.action is AnalystAction.UPGRADE
    assert r.prior_rating == "Hold"
    assert r.rating == "Buy"


def test_parse_empty_fromgrade_is_none():
    payload = [
        {
            "symbol": "AMD",
            "gradeTime": int(datetime(2026, 6, 1).timestamp()),
            "company": "X",
            "fromGrade": "",
            "toGrade": "Buy",
            "action": "init",
        }
    ]
    out = parse_upgrade_downgrade(payload, since=datetime(2026, 1, 1), until=None)
    assert out[0].prior_rating is None
    assert out[0].action is AnalystAction.INIT


def test_fake_source_point_in_time():
    evs = [
        AnalystRating(
            "NVDA",
            "GS",
            "Buy",
            "Hold",
            AnalystAction.UPGRADE,
            None,
            datetime(2026, 6, 1),
            "finnhub",
        ),
        AnalystRating(
            "NVDA",
            "GS",
            "Buy",
            "Hold",
            AnalystAction.UPGRADE,
            None,
            datetime(2027, 1, 1),
            "finnhub",
        ),
    ]
    out = FakeAnalystSource(evs).get_rating_events(
        "NVDA", since=datetime(2026, 1, 1), until=datetime(2026, 12, 31)
    )
    assert len(out) == 1
