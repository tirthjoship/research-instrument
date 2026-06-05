from datetime import datetime

from domain.analyst import AnalystAction, AnalystRating
from domain.analyst_service import analyst_conviction_score, score_firm_accuracy


def _ev(
    firm: str, action: AnalystAction, date: datetime, ticker: str = "NVDA"
) -> AnalystRating:
    return AnalystRating(ticker, firm, "Buy", None, action, None, date, "finnhub")


def test_firm_accuracy_rewards_correct_calls():
    events = [
        _ev("GoodFirm", AnalystAction.UPGRADE, datetime(2026, 1, i + 1))
        for i in range(10)
    ]
    scores = score_firm_accuracy(events, lambda ev: 0.05)  # all upgrades went up
    assert scores["GoodFirm"] == 1.0


def test_firm_low_sample_is_neutral():
    events = [_ev("Rare", AnalystAction.UPGRADE, datetime(2026, 1, 1))]
    scores = score_firm_accuracy(events, lambda ev: 0.05)
    assert scores["Rare"] == 0.5


def test_no_events_neutral():
    assert analyst_conviction_score([], {}, datetime(2026, 6, 4)) == 5.0


def test_fresh_upgrade_by_accurate_firm_raises_score():
    now = datetime(2026, 6, 4)
    ev = _ev("GoodFirm", AnalystAction.UPGRADE, datetime(2026, 6, 3))
    assert analyst_conviction_score([ev], {"GoodFirm": 0.7}, now) > 5.0


def test_downgrade_lowers_score():
    now = datetime(2026, 6, 4)
    ev = _ev("GoodFirm", AnalystAction.DOWNGRADE, datetime(2026, 6, 3))
    assert analyst_conviction_score([ev], {"GoodFirm": 0.7}, now) < 5.0


def test_accurate_firm_beats_unknown_firm():
    now = datetime(2026, 6, 4)
    known = _ev("GoodFirm", AnalystAction.UPGRADE, datetime(2026, 6, 3))
    unknown = _ev("Nobody", AnalystAction.UPGRADE, datetime(2026, 6, 3))
    assert analyst_conviction_score(
        [known], {"GoodFirm": 0.9}, now
    ) > analyst_conviction_score([unknown], {}, now)


def test_stale_event_outside_lookback_ignored():
    now = datetime(2026, 6, 4)
    stale = _ev("GoodFirm", AnalystAction.UPGRADE, datetime(2026, 1, 1))  # >30d old
    assert analyst_conviction_score([stale], {"GoodFirm": 0.9}, now) == 5.0
