"""Holdings and watchlist mixin for SQLiteStore."""

from __future__ import annotations

import sqlite3

from adapters.data.store._base import connect_and_init
from domain.models import Holding


class HoldingsMixin:
    _db_path: str

    def _conn(self) -> sqlite3.Connection:
        return connect_and_init(self._db_path)

    def add_holding(self, holding: Holding) -> None:
        conn = self._conn()
        conn.execute(
            """INSERT OR REPLACE INTO holdings
               (symbol, quantity, purchase_price, purchase_date, notes)
               VALUES (?, ?, ?, ?, ?)""",
            (
                holding.symbol,
                holding.quantity,
                holding.purchase_price,
                holding.purchase_date,
                holding.notes,
            ),
        )
        conn.commit()

    def remove_holding(self, symbol: str) -> None:
        conn = self._conn()
        conn.execute("DELETE FROM holdings WHERE symbol = ?", (symbol,))
        conn.commit()

    def get_holdings(self) -> list[Holding]:
        conn = self._conn()
        rows = conn.execute(
            "SELECT symbol, quantity, purchase_price, purchase_date, notes FROM holdings"
        ).fetchall()
        return [
            Holding(
                symbol=r[0],
                quantity=r[1],
                purchase_price=r[2],
                purchase_date=r[3],
                notes=r[4] or "",
            )
            for r in rows
        ]

    def get_holding(self, symbol: str) -> Holding | None:
        conn = self._conn()
        row = conn.execute(
            "SELECT symbol, quantity, purchase_price, purchase_date, notes FROM holdings WHERE symbol = ?",
            (symbol,),
        ).fetchone()
        if row is None:
            return None
        return Holding(
            symbol=row[0],
            quantity=row[1],
            purchase_price=row[2],
            purchase_date=row[3],
            notes=row[4] or "",
        )

    def add_watchlist(self, symbol: str, notes: str = "") -> None:
        """Add or update a symbol on the watchlist."""
        conn = self._conn()
        conn.execute(
            """INSERT INTO watchlist (symbol, added_date, notes)
               VALUES (?, date('now'), ?)
               ON CONFLICT(symbol) DO UPDATE SET notes = excluded.notes""",
            (symbol.upper(), notes),
        )
        conn.commit()

    def remove_watchlist(self, symbol: str) -> None:
        """Remove a symbol from the watchlist."""
        conn = self._conn()
        conn.execute("DELETE FROM watchlist WHERE symbol = ?", (symbol.upper(),))
        conn.commit()

    def get_watchlist(self) -> list[dict[str, str]]:
        """Return all watchlist items as dicts."""
        conn = self._conn()
        rows = conn.execute(
            "SELECT symbol, added_date, notes FROM watchlist ORDER BY symbol"
        ).fetchall()
        return [
            {
                "symbol": r["symbol"],
                "added_date": r["added_date"],
                "notes": r["notes"] or "",
            }
            for r in rows
        ]
