"""tests/domain/test_adherence_checks.py"""

from datetime import date

from domain.adherence import (
    BufferVerdict,
    ThrottleVerdict,
    cash_buffer_check,
    throttle_check,
)


def test_throttle_ok_under_threshold() -> None:
    r = throttle_check(n_discretionary_trades=2, weeks_elapsed=1.0)
    assert r.verdict is ThrottleVerdict.OK
    assert r.trades_per_week == 2.0


def test_throttle_overtrade_above_threshold() -> None:
    r = throttle_check(n_discretionary_trades=4, weeks_elapsed=1.0)
    assert r.verdict is ThrottleVerdict.OVERTRADE


def test_throttle_exactly_at_threshold_is_ok() -> None:
    assert throttle_check(3, 1.0).verdict is ThrottleVerdict.OK


def test_throttle_gap_week_absorbed() -> None:
    # 4 trades over 2 weeks = 2/week -> OK
    assert throttle_check(4, 2.0).verdict is ThrottleVerdict.OK


def test_buffer_ok() -> None:
    r = cash_buffer_check(
        cash_cad=1000.0,
        portfolio_value_cad=10000.0,
        cash_as_of=date(2026, 6, 1),
        now=date(2026, 6, 13),
    )
    assert r.verdict is BufferVerdict.OK
    assert r.cash_pct == 1000.0 / 11000.0


def test_buffer_breach() -> None:
    r = cash_buffer_check(
        cash_cad=100.0,
        portfolio_value_cad=10000.0,
        cash_as_of=date(2026, 6, 1),
        now=date(2026, 6, 13),
    )
    assert r.verdict is BufferVerdict.BUFFER_BREACH


def test_buffer_stale_cash_beats_breach() -> None:
    r = cash_buffer_check(
        cash_cad=100.0,
        portfolio_value_cad=10000.0,
        cash_as_of=date(2026, 1, 1),
        now=date(2026, 6, 13),
    )
    assert r.verdict is BufferVerdict.STALE_CASH


def test_buffer_missing_portfolio_value_is_stale() -> None:
    r = cash_buffer_check(
        cash_cad=1000.0,
        portfolio_value_cad=None,
        cash_as_of=date(2026, 6, 1),
        now=date(2026, 6, 13),
    )
    assert r.verdict is BufferVerdict.STALE_CASH
