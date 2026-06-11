"""tests/domain/test_adherence_diff.py"""

from datetime import date

from hypothesis import given
from hypothesis import strategies as st

from domain.adherence import DetectedTrade, TradeAction, diff_holdings

WEEK = date(2026, 6, 13)


def test_no_change_no_trades() -> None:
    h = {"AC.TO": 30.0, "ARKK": 12.0}
    assert diff_holdings(h, h, WEEK) == []


def test_new_position_detected() -> None:
    trades = diff_holdings({}, {"AC.TO": 30.0}, WEEK)
    assert trades == [DetectedTrade("AC.TO", TradeAction.NEW, 0.0, 30.0, WEEK)]


def test_exit_position_detected() -> None:
    trades = diff_holdings({"AC.TO": 30.0}, {}, WEEK)
    assert trades == [DetectedTrade("AC.TO", TradeAction.EXIT, 30.0, 0.0, WEEK)]


def test_sell_above_threshold_detected() -> None:
    trades = diff_holdings({"AC.TO": 100.0}, {"AC.TO": 50.0}, WEEK)
    assert trades[0].action is TradeAction.SELL


def test_sell_below_threshold_filtered() -> None:
    # 0.3% decrease < 0.5% sell filter
    assert diff_holdings({"AC.TO": 1000.0}, {"AC.TO": 997.0}, WEEK) == []


def test_drip_sized_buy_filtered() -> None:
    # 1% increase < 2% BUY/DRIP filter
    assert diff_holdings({"AC.TO": 100.0}, {"AC.TO": 101.0}, WEEK) == []


def test_buy_above_drip_band_detected() -> None:
    trades = diff_holdings({"AC.TO": 100.0}, {"AC.TO": 110.0}, WEEK)
    assert trades[0].action is TradeAction.BUY


def test_two_for_one_split_flagged_not_buy() -> None:
    trades = diff_holdings({"AC.TO": 100.0}, {"AC.TO": 200.0}, WEEK)
    assert trades[0].action is TradeAction.SUSPECTED_SPLIT


def test_reverse_split_flagged_not_sell() -> None:
    trades = diff_holdings({"AC.TO": 100.0}, {"AC.TO": 50.5}, WEEK)
    # 0.505 ratio is within ±2% of 0.5 -> split, not SELL
    assert trades[0].action is TradeAction.SUSPECTED_SPLIT


@given(
    st.dictionaries(st.text(min_size=1, max_size=6), st.floats(1.0, 1e6), max_size=20)
)
def test_property_self_diff_is_empty(holdings: dict[str, float]) -> None:
    assert diff_holdings(holdings, holdings, WEEK) == []


@given(
    prev=st.floats(1.0, 1e6),
    curr=st.floats(1.0, 1e6),
)
def test_property_every_trade_has_real_change(prev: float, curr: float) -> None:
    trades = diff_holdings({"X": prev}, {"X": curr}, WEEK)
    for t in trades:
        assert t.qty_before != t.qty_after
