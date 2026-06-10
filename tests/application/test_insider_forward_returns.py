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
    resolved, unresolved = resolve_events([ev], lambda tk: series.get(tk, []))
    assert unresolved == []
    assert resolved[0]["ticker"] == "ABC"
    assert abs(resolved[0]["fwd_return"] - 0.10) < 1e-9
    assert resolved[0]["adv"] > 0
    assert "entry_date" in resolved[0] and "exit_date" in resolved[0]


def test_missing_prices_recorded_unresolved_not_dropped():
    ev = ClusterEvent("ZZZ", date(2020, 1, 1), 3, 1000.0)
    resolved, unresolved = resolve_events([ev], lambda tk: [])
    assert resolved == []
    assert unresolved == [ev]


def test_benchmark_return_over_window():
    series = {"IWC": _prices(date(2020, 1, 1), [100.0] * 22 + [110.0] * 10, [1.0] * 32)}
    r = benchmark_return(
        lambda tk: series.get(tk, []), "IWC", date(2020, 1, 1), date(2020, 1, 23)
    )
    assert r is not None and abs(r - 0.10) < 1e-9
