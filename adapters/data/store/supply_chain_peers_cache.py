"""Supply-chain peers cache mixin for SQLiteStore.

Persists FMP `stock-peers` results with a TTL so repeat dashboard page
loads for the same ticker don't re-hit the API. Mirrors buzz_signals.py's
mixin shape. Deliberately never caches an empty peers list (see
put_cached_peers's docstring) — matches PR #148's `_no_stale_empty`
precedent of never trusting an empty result as cache-worthy.
"""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime

from adapters.data.store._base import connect_and_init, to_naive_utc


class SupplyChainPeersCacheMixin:
    _db_path: str

    def _conn(self) -> sqlite3.Connection:
        return connect_and_init(self._db_path)

    def put_cached_peers(
        self, ticker: str, peers: list[str], fetched_at: datetime
    ) -> None:
        """Persist *peers* for *ticker*. A no-op on an empty list — an empty
        peers result is indistinguishable from a live-fetch failure (see
        adapters/data/fmp_adapter.py's get_cached_stock_peers), so it must
        never be written here either, even if a future caller bypasses that
        wrapper's own guard."""
        if not peers:
            return
        conn = self._conn()
        conn.execute(
            "INSERT OR REPLACE INTO supply_chain_peers_cache "
            "(ticker, peers_json, fetched_at) VALUES (?, ?, ?)",
            (ticker, json.dumps(peers), to_naive_utc(fetched_at).isoformat()),
        )
        conn.commit()

    def get_cached_peers(
        self, ticker: str, now: datetime, ttl_hours: float = 24.0
    ) -> list[str] | None:
        conn = self._conn()
        row = conn.execute(
            "SELECT peers_json, fetched_at FROM supply_chain_peers_cache WHERE ticker = ?",
            (ticker,),
        ).fetchone()
        if row is None:
            return None
        now_naive = to_naive_utc(now)
        fetched = to_naive_utc(datetime.fromisoformat(row["fetched_at"]))
        if (now_naive - fetched).total_seconds() > ttl_hours * 3600:
            return None
        peers: list[str] = json.loads(row["peers_json"])
        return peers
