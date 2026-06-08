def test_daily_returns():
    from domain.backtest_metrics import daily_returns

    assert daily_returns([100.0, 110.0, 99.0]) == [0.1, -0.1]


def test_cagr_doubling_over_one_year():
    from domain.backtest_metrics import cagr

    assert abs(cagr([1.0, 2.0], periods_per_year=1) - 1.0) < 1e-9


def test_sharpe_positive_for_steady_gains():
    from domain.backtest_metrics import sharpe

    rets = [0.001] * 252
    assert sharpe(rets, periods_per_year=252) > 0


def test_sharpe_zero_variance_returns_zero():
    from domain.backtest_metrics import sharpe

    assert sharpe([0.0, 0.0, 0.0]) == 0.0


def test_max_drawdown_simple():
    from domain.backtest_metrics import max_drawdown

    assert abs(max_drawdown([100.0, 120.0, 72.0, 90.0]) - 0.40) < 1e-9


def test_max_drawdown_monotonic_up_is_zero():
    from domain.backtest_metrics import max_drawdown

    assert max_drawdown([1.0, 2.0, 3.0]) == 0.0
