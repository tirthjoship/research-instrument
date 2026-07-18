"""Tests for SupplyChainPeersCacheMixin."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from adapters.data.sqlite_store import SQLiteStore


def test_peers_cache_hit_and_ttl(tmp_path: pytest.TempPathFactory) -> None:
    store = SQLiteStore(str(tmp_path / "t.db"))  # type: ignore[arg-type]
    t0 = datetime(2026, 7, 17, 8, 0, 0)
    store.put_cached_peers("RY.TO", ["BMO.TO", "BNS.TO"], t0)

    # fresh within TTL
    assert store.get_cached_peers("RY.TO", t0 + timedelta(hours=1), ttl_hours=24) == [
        "BMO.TO",
        "BNS.TO",
    ]
    # expired beyond TTL
    assert (
        store.get_cached_peers("RY.TO", t0 + timedelta(hours=25), ttl_hours=24) is None
    )
    # missing key
    assert store.get_cached_peers("ZZZZ", t0, ttl_hours=24) is None


def test_peers_cache_handles_aware_now(tmp_path: pytest.TempPathFactory) -> None:
    store = SQLiteStore(db_path=str(tmp_path / "t.db"))  # type: ignore[arg-type]
    t0 = datetime(2026, 7, 17, 8, 0, 0)  # naive store
    store.put_cached_peers("FORCEMOT.NS", ["ASAHIINDIA.NS"], t0)
    aware_now = datetime(2026, 7, 17, 9, 0, 0, tzinfo=timezone.utc)
    assert store.get_cached_peers("FORCEMOT.NS", aware_now, ttl_hours=24) == [
        "ASAHIINDIA.NS"
    ]


def test_peers_cache_overwrites_on_replace(tmp_path: pytest.TempPathFactory) -> None:
    store = SQLiteStore(str(tmp_path / "t.db"))  # type: ignore[arg-type]
    t0 = datetime(2026, 7, 17, 8, 0, 0)
    store.put_cached_peers("RY.TO", ["BMO.TO"], t0)
    store.put_cached_peers("RY.TO", ["BMO.TO", "BNS.TO"], t0 + timedelta(minutes=5))
    assert store.get_cached_peers(
        "RY.TO", t0 + timedelta(minutes=10), ttl_hours=24
    ) == [
        "BMO.TO",
        "BNS.TO",
    ]
