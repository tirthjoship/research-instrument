"""Tests for ScanCache — smart TTL (15min market hours, 60min after hours)."""

from datetime import datetime
from zoneinfo import ZoneInfo

from adapters.visualization.cache import ScanCache, _is_market_hours

ET = ZoneInfo("America/New_York")


def make_et(hour: int, minute: int = 0) -> datetime:
    """Return a timezone-aware datetime in ET for a fixed weekday (Monday)."""
    return datetime(2026, 6, 1, hour, minute, tzinfo=ET)  # 2026-06-01 is a Monday


class TestIsMarketHours:
    def test_market_open_930(self):
        assert _is_market_hours(make_et(9, 30)) is True

    def test_market_close_1600(self):
        # 16:00 ET is NOT market hours (market closes at 16:00, exclusive)
        assert _is_market_hours(make_et(16, 0)) is False

    def test_mid_day(self):
        assert _is_market_hours(make_et(13, 0)) is True

    def test_before_open(self):
        assert _is_market_hours(make_et(9, 0)) is False

    def test_after_close(self):
        assert _is_market_hours(make_et(20, 0)) is False


class TestScanCacheEmpty:
    def test_empty_cache_is_stale(self):
        cache = ScanCache()
        assert cache.is_stale() is True

    def test_empty_get_results(self):
        cache = ScanCache()
        assert cache.get_results() == []

    def test_empty_last_scan_time_is_none(self):
        cache = ScanCache()
        assert cache.last_scan_time() is None


class TestScanCacheFresh:
    def test_fresh_cache_not_stale_after_hours(self):
        cache = ScanCache()
        # Store at 20:00 ET (after hours) — TTL is 60 min
        stored_at = make_et(20, 0)
        cache.store(["AAPL", "GOOG"], stored_at)
        now = make_et(20, 30)  # 30 min later — not stale
        assert cache.is_stale(now) is False

    def test_fresh_cache_not_stale_market_hours(self):
        cache = ScanCache()
        # Store at 10:00 ET (market hours) — TTL is 15 min
        stored_at = make_et(10, 0)
        cache.store(["AAPL"], stored_at)
        now = make_et(10, 10)  # 10 min later — not stale
        assert cache.is_stale(now) is False


class TestScanCacheStale:
    def test_stale_after_61_minutes_after_hours(self):
        cache = ScanCache()
        stored_at = make_et(20, 0)
        cache.store(["AAPL"], stored_at)
        now = make_et(21, 1)  # 61 min later — stale (TTL = 60 min)
        assert cache.is_stale(now) is True

    def test_stale_after_16_minutes_market_hours(self):
        cache = ScanCache()
        stored_at = make_et(10, 0)
        cache.store(["AAPL"], stored_at)
        now = make_et(10, 16)  # 16 min later — stale (TTL = 15 min)
        assert cache.is_stale(now) is True

    def test_not_stale_after_30_minutes_after_hours(self):
        cache = ScanCache()
        stored_at = make_et(20, 0)
        cache.store(["AAPL"], stored_at)
        now = make_et(20, 30)  # 30 min later — not stale (TTL = 60 min)
        assert cache.is_stale(now) is False


class TestScanCacheGetResults:
    def test_get_results_returns_stored_data(self):
        cache = ScanCache()
        data = [{"ticker": "AAPL", "score": 0.9}, {"ticker": "GOOG", "score": 0.7}]
        cache.store(data, make_et(10, 0))
        assert cache.get_results() == data

    def test_store_overwrites_previous(self):
        cache = ScanCache()
        cache.store(["AAPL"], make_et(10, 0))
        cache.store(["GOOG"], make_et(10, 20))
        assert cache.get_results() == ["GOOG"]


class TestMinutesAgo:
    def test_minutes_ago_approximately_correct(self):
        cache = ScanCache()
        cache.store(["AAPL"], make_et(10, 0))
        # minutes_ago uses real datetime.now() so we can't pass a fixed time.
        # We test indirectly: store then immediately call — should be ~0
        cache2 = ScanCache()
        cache2.store(["X"], datetime.now(tz=ET))
        assert cache2.minutes_ago() <= 1  # fresh store — under 1 minute


class TestLastScanTime:
    def test_last_scan_time_formatted(self):
        cache = ScanCache()
        cache.store(["AAPL"], make_et(14, 35))
        result = cache.last_scan_time()
        assert result is not None
        assert "02:35 PM" in result or "2:35 PM" in result

    def test_last_scan_time_none_when_empty(self):
        cache = ScanCache()
        assert cache.last_scan_time() is None
