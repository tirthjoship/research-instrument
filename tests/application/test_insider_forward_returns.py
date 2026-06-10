from datetime import date, timedelta

from application.insider_forward_returns import benchmark_return, resolve_events
from domain.insider_cluster import ClusterEvent


def _prices(start, closes, vols):
    return [
        (start + timedelta(days=i), c, v) for i, (c, v) in enumerate(zip(closes, vols))
    ]


def test_forward_return_and_adv_computed():
    ev = ClusterEvent("ABC", date(2020, 1, 1), 3, 1000.0)
    closes = [10.0] * 22 + [11.0] * 10
    closes[21] = 11.0
    vols = [1000.0] * len(closes)
    series = {"ABC": _prices(date(2020, 1, 1), closes, vols)}
    records, no_price = resolve_events([ev], lambda tk: series.get(tk, []))
    assert no_price == []
    assert records[0]["ticker"] == "ABC"
    assert abs(records[0]["fwd_return"] - 0.10) < 1e-9
    assert records[0]["adv"] > 0
    assert records[0]["entry_date"] is not None
    assert records[0]["exit_date"] is not None


def test_no_price_event_goes_to_no_price_not_dropped():
    ev = ClusterEvent("ZZZ", date(2020, 1, 1), 3, 1000.0)
    records, no_price = resolve_events([ev], lambda tk: [])
    assert records == []
    assert no_price == [ev]


def test_delisted_midwindow_has_adv_but_no_forward():
    # Prices exist at/after the fire date but fewer than 21 forward bars (delisted
    # mid-holding-period). C1: must still get a trailing ADV (tercile-assignable),
    # with fwd_return None so it lands in the coverage denominator, not the numerator.
    ev = ClusterEvent("DEAD", date(2020, 2, 1), 3, 1000.0)
    # 40 bars BEFORE the fire date (ample trailing), then only 5 bars after.
    closes = [10.0] * 45
    vols = [1000.0] * 45
    series = {"DEAD": _prices(date(2020, 1, 1), closes, vols)}
    records, no_price = resolve_events([ev], lambda tk: series.get(tk, []))
    assert no_price == []
    assert len(records) == 1
    assert records[0]["adv"] > 0  # trailing ADV computed
    assert records[0]["fwd_return"] is None  # no usable forward window
    assert records[0]["entry_date"] is None


def test_benchmark_return_over_window():
    series = {"IWC": _prices(date(2020, 1, 1), [100.0] * 22 + [110.0] * 10, [1.0] * 32)}
    r = benchmark_return(
        lambda tk: series.get(tk, []), "IWC", date(2020, 1, 1), date(2020, 1, 23)
    )
    assert r is not None and abs(r - 0.10) < 1e-9


def test_nan_adv_routes_to_no_price():
    # A NaN bar in the lookback would silently corrupt sorted-rank tercile
    # binning; resolve_events must route the event to the conservative
    # no_price (bottom-denominator) path instead.
    from domain.insider_cluster import ClusterEvent

    ev = ClusterEvent(
        ticker="NAN",
        fire_date=date(2020, 2, 1),
        distinct_insiders=3,
        total_buy_value=1.0,
    )
    series = [
        (date(2020, 1, 1) + timedelta(days=i), float("nan"), 100.0) for i in range(60)
    ]
    records, no_price = resolve_events([ev], lambda tk: series)
    assert records == []
    assert no_price == [ev]
