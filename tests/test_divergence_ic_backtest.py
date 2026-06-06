"""Tests for DivergenceICBacktestUseCase — Task 3 of Leg-2 Sub-Project D."""

from datetime import datetime, timedelta, timezone


def _attn(now, ticker, recent_val, base_val=10.0):
    pts = [(now - timedelta(days=d), base_val) for d in range(8, 35)]
    pts += [(now - timedelta(days=d), recent_val) for d in range(0, 7)]
    return [(t, v) for t, v in pts]


def test_ic_backtest_detects_positive_signal():
    from application.divergence_ic_backtest import DivergenceICBacktestUseCase

    now = datetime(2026, 1, 5, tzinfo=timezone.utc)
    dates = [now + timedelta(days=7 * k) for k in range(8)]
    tickers = [f"T{i}" for i in range(60)]

    def attn_fn(ticker, t):
        i = int(ticker[1:])
        return _attn(t, ticker, 90.0 if i % 2 == 0 else 10.0)

    def price_fn(ticker, t):
        return [(t - timedelta(days=d), 100.0) for d in range(0, 40)]

    def fwd_fn(ticker, t):
        i = int(ticker[1:])
        return 0.05 if i % 2 == 0 else -0.01

    uc = DivergenceICBacktestUseCase(
        attention_fn=attn_fn, price_fn=price_fn, forward_return_fn=fwd_fn, min_names=50
    )
    report = uc.execute(dates, tickers, horizon_label="1m")
    assert report["mean_ic"] > 0.2
    assert report["n_dates"] >= 1
    assert "bootstrap" in report and "date_level" in report


def test_ic_backtest_noise_signal_near_zero():
    from application.divergence_ic_backtest import DivergenceICBacktestUseCase

    now = datetime(2026, 1, 5, tzinfo=timezone.utc)
    dates = [now + timedelta(days=7 * k) for k in range(8)]
    tickers = [f"T{i}" for i in range(60)]

    def attn_fn(ticker, t):
        i = int(ticker[1:])
        return _attn(t, ticker, 90.0 if i % 2 == 0 else 10.0)

    def price_fn(ticker, t):
        return [(t - timedelta(days=d), 100.0) for d in range(0, 40)]

    def fwd_fn(ticker, t):
        i = int(ticker[1:])
        return 0.03 if i % 3 == 0 else -0.01

    uc = DivergenceICBacktestUseCase(
        attention_fn=attn_fn, price_fn=price_fn, forward_return_fn=fwd_fn, min_names=50
    )
    report = uc.execute(dates, tickers, horizon_label="1m")
    assert abs(report["mean_ic"]) < 0.2
