"""Tests for yfinance analyst-history adapter — pure parse helper, no network."""

from datetime import datetime

from adapters.data.yfinance_analyst_adapter import parse_yf_upgrades
from domain.analyst import AnalystAction


def test_parse_maps_and_filters_point_in_time():
    records = [
        {
            "GradeDate": datetime(2024, 3, 1),
            "Firm": "Morgan Stanley",
            "ToGrade": "Overweight",
            "FromGrade": "Equal-Weight",
            "Action": "up",
        },
        {
            "GradeDate": datetime(2026, 9, 1),
            "Firm": "Future Co",
            "ToGrade": "Buy",
            "FromGrade": "Hold",
            "Action": "up",
        },  # after `until`
    ]
    out = parse_yf_upgrades(
        records, "NVDA", since=datetime(2024, 1, 1), until=datetime(2026, 6, 1)
    )
    assert len(out) == 1
    r = out[0]
    assert r.ticker == "NVDA"
    assert r.firm == "Morgan Stanley"
    assert r.action is AnalystAction.UPGRADE
    assert r.prior_rating == "Equal-Weight"
    assert r.rating == "Overweight"
    assert r.published_at == datetime(2024, 3, 1)


def test_parse_action_mapping_and_empty_fromgrade():
    records = [
        {
            "GradeDate": datetime(2025, 1, 1),
            "Firm": "X",
            "ToGrade": "Buy",
            "FromGrade": "",
            "Action": "init",
        },
        {
            "GradeDate": datetime(2025, 2, 1),
            "Firm": "Y",
            "ToGrade": "Hold",
            "FromGrade": "Buy",
            "Action": "down",
        },
        {
            "GradeDate": datetime(2025, 3, 1),
            "Firm": "Z",
            "ToGrade": "Buy",
            "FromGrade": "Buy",
            "Action": "main",
        },
    ]
    out = parse_yf_upgrades(records, "AMD", since=datetime(2024, 1, 1), until=None)
    assert [r.action for r in out] == [
        AnalystAction.INIT,
        AnalystAction.DOWNGRADE,
        AnalystAction.MAINTAIN,
    ]
    assert out[0].prior_rating is None


def test_parse_handles_string_dates():
    records = [
        {
            "GradeDate": "2025-05-01",
            "Firm": "X",
            "ToGrade": "Buy",
            "FromGrade": "Hold",
            "Action": "up",
        }
    ]
    out = parse_yf_upgrades(records, "NVDA", since=datetime(2024, 1, 1), until=None)
    assert out[0].published_at == datetime(2025, 5, 1)
