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


def test_verdict_proceed_when_better_sharpe_and_lower_dd(monkeypatch):
    from application import momentum_exit_backtest as m

    uc = m.MomentumExitBacktestUseCase(price_provider=lambda t: [])
    report = {
        "strategy": {
            "sharpe": 1.2,
            "max_drawdown": 0.20,
            "equity": [1.0, 1.1, 1.2],
            "cagr": 0.1,
            "sortino": 1.5,
        },
        "buy_hold": {
            "sharpe": 0.6,
            "max_drawdown": 0.50,
            "equity": [1.0, 0.9, 1.1],
            "cagr": 0.1,
            "sortino": 0.7,
        },
    }
    verdict = uc.verdict(report, sharpe_diff_ci_low=0.1)  # CI excludes 0
    assert verdict["decision"] == "PROCEED"
    assert verdict["drawdown_reduction"] >= 0.30


def test_verdict_kill_when_dd_not_reduced_enough():
    from application import momentum_exit_backtest as m

    uc = m.MomentumExitBacktestUseCase(price_provider=lambda t: [])
    report = {
        "strategy": {
            "sharpe": 1.2,
            "max_drawdown": 0.45,
            "equity": [1.0],
            "cagr": 0,
            "sortino": 0,
        },
        "buy_hold": {
            "sharpe": 0.6,
            "max_drawdown": 0.50,
            "equity": [1.0],
            "cagr": 0,
            "sortino": 0,
        },
    }
    verdict = uc.verdict(report, sharpe_diff_ci_low=0.1)
    assert verdict["decision"] == "KILL"  # only 10% dd reduction < 30%


def test_transaction_costs_reduce_strategy_return():
    from datetime import datetime, timedelta, timezone

    from application.momentum_exit_backtest import MomentumExitBacktestUseCase

    start = datetime(2020, 1, 1, tzinfo=timezone.utc)
    vals = list(range(100, 500)) + list(range(500, 480, -1))
    prices = {"A": [(start + timedelta(days=i), float(v)) for i, v in enumerate(vals)]}

    def prov(t):
        return prices.get(t, [])

    free = MomentumExitBacktestUseCase(prov, cost_per_trade=0.0).execute(
        ["A"], start, start + timedelta(days=len(vals))
    )
    costed = MomentumExitBacktestUseCase(prov, cost_per_trade=0.01).execute(
        ["A"], start, start + timedelta(days=len(vals))
    )
    assert costed["strategy"]["equity"][-1] <= free["strategy"]["equity"][-1]
