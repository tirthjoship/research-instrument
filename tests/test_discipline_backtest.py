import random
from datetime import datetime, timedelta, timezone


def _volatile_falling_series(start: datetime) -> list[tuple[datetime, float]]:
    """Calm uptrend (250 days) followed by volatile decline (300 days).
    The elevated recent volatility relative to the calm-trend baseline is what
    triggers conditional_vol_signal > 0, which causes grade_position to emit
    REDUCE (not TRIM) in the decline phase."""
    random.seed(0)
    up = [100.0 + i * 0.5 for i in range(250)]
    down: list[float] = []
    price = up[-1]
    for _ in range(300):
        price = max(30.0, price + (-8.0 + random.uniform(-3.0, 1.0)))
        down.append(price)
    vals = up + down
    return [(start + timedelta(days=i), v) for i, v in enumerate(vals)]


def test_backtest_calibration_reduce_flags_precede_drops_on_falling_name():
    from application.discipline_backtest import backtest_discipline_calibration

    start = datetime(2020, 1, 1, tzinfo=timezone.utc)
    name_series = _volatile_falling_series(start)
    n = len(name_series)
    spy_vals = [100.0 + i * 0.2 for i in range(n)]
    spy_series = [(start + timedelta(days=i), v) for i, v in enumerate(spy_vals)]
    series = {"DOWN": name_series, "SPY": spy_series}
    out = backtest_discipline_calibration(
        ["DOWN"],
        lambda t: series.get(t, []),
        start,
        start + timedelta(days=n),
        step_days=10,
        horizon_days=21,
    )
    assert out["total_verdicts"] > 0
    assert "REDUCE" in out["by_verdict"]
    assert out["by_verdict"]["REDUCE"]["down_rate"] >= 0.5
    # ADR-048: directional Brier is REDUCE-only (TRIM excluded — position-sizing)
    assert 0.0 <= out["brier_reduce"] <= 1.0
    assert out["n_reduce"] >= 0


def test_backtest_calibration_empty_when_no_history():
    from application.discipline_backtest import backtest_discipline_calibration

    start = datetime(2020, 1, 1, tzinfo=timezone.utc)
    out = backtest_discipline_calibration(
        ["X"], lambda t: [], start, start + timedelta(days=10)
    )
    assert out["total_verdicts"] == 0
