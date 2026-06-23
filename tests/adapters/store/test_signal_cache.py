"""Tests for SignalCacheMixin."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from adapters.data.sqlite_store import SQLiteStore


def test_signal_cache_hit_and_ttl(tmp_path: pytest.TempPathFactory) -> None:
    store = SQLiteStore(str(tmp_path / "t.db"))  # type: ignore[arg-type]
    t0 = datetime(2026, 6, 5, 8, 0, 0)
    store.put_cached_signal("ASTS", "event_signal", 7.0, t0)

    # fresh within TTL
    assert (
        store.get_cached_signal(
            "ASTS", "event_signal", t0 + timedelta(hours=1), ttl_hours=24
        )
        == 7.0
    )
    # expired beyond TTL
    assert (
        store.get_cached_signal(
            "ASTS", "event_signal", t0 + timedelta(hours=25), ttl_hours=24
        )
        is None
    )
    # missing key
    assert store.get_cached_signal("ZZZ", "event_signal", t0, ttl_hours=24) is None


def test_signal_cache_handles_aware_now(tmp_path: pytest.TempPathFactory) -> None:
    store = SQLiteStore(db_path=str(tmp_path / "t.db"))  # type: ignore[arg-type]
    t0 = datetime(2026, 6, 5, 8, 0, 0)  # naive store
    store.put_cached_signal("ASTS", "event_signal", 7.0, t0)
    # aware now within TTL — must not raise, must hit
    aware_now = datetime(2026, 6, 5, 9, 0, 0, tzinfo=timezone.utc)
    assert (
        store.get_cached_signal("ASTS", "event_signal", aware_now, ttl_hours=24) == 7.0
    )
