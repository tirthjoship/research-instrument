"""Tests for MomentumExitBacktestUseCase — Task 6."""

from datetime import datetime, timedelta, timezone


def _daily(start, vals):
    return [(start + timedelta(days=i), float(v)) for i, v in enumerate(vals)]


def test_strategy_exits_on_trend_break_cuts_drawdown():
    from application.momentum_exit_backtest import MomentumExitBacktestUseCase

    start = datetime(2020, 1, 1, tzinfo=timezone.utc)
    up = list(range(100, 300)) + list(range(300, 150, -1))  # up then crash
    prices = {"WIN": _daily(start, up)}

    def provider(t):
        return prices.get(t, [])

    uc = MomentumExitBacktestUseCase(price_provider=provider)
    report = uc.execute(["WIN"], start, start + timedelta(days=len(up)))
    assert report["strategy"]["max_drawdown"] < report["buy_hold"]["max_drawdown"]
    assert "equity" in report["strategy"]


def test_strategy_pays_for_the_triggering_crash_bar_no_lookahead():
    """Regression: a stop seen on day t must still cost the day-t move.

    The buggy code updated `held` before booking the return, so the strategy
    dodged the very bar that triggered the stop — showing ~0 max_drawdown on a
    50% single-bar cliff. The correct code books the return first (using the
    prior-day held state) and only then fires the stop for day t+1.
    """
    from datetime import timezone

    from application.momentum_exit_backtest import MomentumExitBacktestUseCase

    start = datetime(2020, 1, 1, tzinfo=timezone.utc)
    # ~400 trading days of steady uptrend so the name passes the 200d SMA filter
    # and accumulates enough monthly closes for momentum (needs >=13 months).
    # Then a single-bar 50% cliff on the last day.
    vals = list(range(100, 501)) + [250]  # 400 up-bars then halves to 250
    prices = {"CLIFF": _daily(start, vals)}

    def provider(t: str) -> list[tuple[datetime, float]]:
        return prices.get(t, [])

    uc = MomentumExitBacktestUseCase(price_provider=provider)
    report = uc.execute(["CLIFF"], start, start + timedelta(days=len(vals)))

    # The strategy held CLIFF going into the cliff bar, so it MUST absorb a
    # large drop on that bar — it cannot exit before paying for the move that
    # triggers the stop.  ~0 drawdown would indicate look-ahead bias.
    assert report["strategy"]["max_drawdown"] > 0.15, (
        f"Expected strategy to absorb the cliff-bar drop (max_drawdown > 0.15) "
        f"but got {report['strategy']['max_drawdown']:.4f}. "
        "This indicates look-ahead bias: the stop fired before the loss was booked."
    )
