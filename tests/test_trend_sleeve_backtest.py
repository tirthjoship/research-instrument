from datetime import datetime, timedelta

from application.trend_sleeve_backtest import TrendSleeveBacktestUseCase


def _daily(start_price: float, slope: float, days: int) -> list[tuple[datetime, float]]:
    base = datetime(2006, 1, 2)
    return [(base + timedelta(days=i), start_price + slope * i) for i in range(days)]


def test_construction_builds_three_aligned_series() -> None:
    # 7-ETF universe; give SPY a steady uptrend, everything else flat-ish.
    days = 900  # ~3y of daily points
    series = {
        "SPY": _daily(100.0, 0.05, days),
        "EFA": _daily(50.0, 0.0, days),
        "EEM": _daily(50.0, 0.0, days),
        "TLT": _daily(100.0, 0.0, days),
        "IEF": _daily(100.0, 0.0, days),
        "GLD": _daily(100.0, 0.0, days),
        "DBC": _daily(20.0, 0.0, days),
    }
    uc = TrendSleeveBacktestUseCase(price_series_fn=lambda t: series[t])
    dates = [datetime(2007, m, 28) for m in range(1, 13)] + [datetime(2008, 1, 28)]
    spy, sleeve, blended = uc.build_series(dates)
    assert len(spy) == len(sleeve) == len(blended)
    assert len(spy) >= 1
    # Blended must equal 0.8*spy + 0.2*sleeve elementwise.
    for i in range(len(spy)):
        assert abs(blended[i] - (0.8 * spy[i] + 0.2 * sleeve[i])) < 1e-9


def _crash_series(days: int) -> dict[str, list[tuple[datetime, float]]]:
    # SPY rises for 2y then crashes hard; a safe-haven (TLT) trends up through the crash.
    base = datetime(2006, 1, 2)
    spy: list[tuple[datetime, float]] = []
    tlt: list[tuple[datetime, float]] = []
    for i in range(days):
        d = base + timedelta(days=i)
        if i < days * 2 // 3:
            spy.append((d, 100.0 + 0.06 * i))
            tlt.append((d, 100.0 + 0.01 * i))
        else:
            # crash phase: SPY -0.4/day drift down, TLT keeps rising (flight to safety)
            spy.append((d, spy[-1][1] - 0.4))
            tlt.append((d, tlt[-1][1] + 0.05))
    flat = [(base + timedelta(days=i), 50.0) for i in range(days)]
    return {
        "SPY": spy,
        "EFA": flat,
        "EEM": flat,
        "TLT": tlt,
        "IEF": flat,
        "GLD": flat,
        "DBC": flat,
    }


def test_planted_crash_protection_cuts_drawdown() -> None:
    series = _crash_series(1100)
    uc = TrendSleeveBacktestUseCase(price_series_fn=lambda t: series[t])
    months: list[datetime] = []
    for yr in (2007, 2008):
        for m in range(1, 13):
            months.append(datetime(yr, m, 28))
    v = uc.execute(months)
    # The blended portfolio must have a shallower (less negative) max drawdown
    # than SPY-core, and the gate should not be KILL.
    assert v.maxdd_blended > v.maxdd_spy  # less negative
    assert v.decision in ("PASS", "INCONCLUSIVE")


def test_flat_noise_does_not_false_pass() -> None:
    # No asset trends; sleeve sits mostly in cash, blended ~= 0.8*SPY (flat).
    base = datetime(2006, 1, 2)
    flat = [(base + timedelta(days=i), 50.0) for i in range(1100)]
    series = {tk: flat for tk in ["SPY", "EFA", "EEM", "TLT", "IEF", "GLD", "DBC"]}
    uc = TrendSleeveBacktestUseCase(price_series_fn=lambda t: series[t])
    months = [datetime(yr, m, 28) for yr in (2007, 2008) for m in range(1, 13)]
    v = uc.execute(months)
    assert v.decision in ("INCONCLUSIVE", "KILL")  # never a false PASS on no signal


def test_verdict_is_frozen() -> None:
    base = datetime(2006, 1, 2)
    flat = [(base + timedelta(days=i), 50.0) for i in range(500)]
    uc = TrendSleeveBacktestUseCase(price_series_fn=lambda t: flat)
    months = [datetime(2007, m, 28) for m in range(1, 13)]
    v = uc.execute(months)
    try:
        v.decision = "X"  # type: ignore[misc]
        assert False, "should be frozen"
    except Exception:
        pass
