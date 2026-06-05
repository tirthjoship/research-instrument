from datetime import datetime


class _MemStore:
    def __init__(self):
        self.data = {}

    def get_cached_signal(self, ticker, dim, now, ttl_hours):
        return self.data.get((ticker, dim))

    def put_cached_signal(self, ticker, dim, value, computed_at):
        self.data[(ticker, dim)] = value


def test_cache_miss_computes_and_stores():
    from application.conviction_signal_cache import ConvictionSignalCache

    store = _MemStore()
    calls = {"n": 0}

    def compute(ticker, now):
        calls["n"] += 1
        return 7.0

    csc = ConvictionSignalCache(store=store, ttl_hours=24)
    v = csc.get_or_compute("ASTS", "event_signal", datetime(2026, 6, 5), compute)
    assert v == 7.0 and calls["n"] == 1
    # second call hits cache
    v2 = csc.get_or_compute("ASTS", "event_signal", datetime(2026, 6, 5), compute)
    assert v2 == 7.0 and calls["n"] == 1


def test_cache_failure_returns_flagged_neutral():
    from application.conviction_signal_cache import ConvictionSignalCache

    store = _MemStore()

    def compute(ticker, now):
        raise RuntimeError("api down")

    csc = ConvictionSignalCache(store=store, ttl_hours=24)
    v = csc.get_or_compute("ASTS", "event_signal", datetime(2026, 6, 5), compute)
    assert v == 5.0
    assert ("ASTS", "event_signal") in csc.flags  # flagged, not silent
