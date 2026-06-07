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
