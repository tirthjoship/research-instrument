"""Tracked trades and outcomes mixin for SQLiteStore."""

from __future__ import annotations

import json
import sqlite3
from typing import Any

from adapters.data.store._base import connect_and_init
from domain.outcome import TrackedTrade, TradeAction, TradeOutcome


class TradesMixin:
    _db_path: str

    def _conn(self) -> sqlite3.Connection:
        return connect_and_init(self._db_path)

    def save_trade(self, trade: TrackedTrade) -> None:
        conn = self._conn()
        conn.execute(
            """INSERT OR REPLACE INTO tracked_trades
            (trade_id, ticker, action, price, quantity, trade_date,
             conviction_at_trade, signals_at_trade, opportunity_card_id, notes)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                trade.trade_id,
                trade.ticker,
                trade.action.value,
                trade.price,
                trade.quantity,
                trade.trade_date,
                trade.conviction_at_trade,
                json.dumps(trade.signals_at_trade),
                trade.opportunity_card_id,
                trade.notes,
            ),
        )
        conn.commit()

    def get_trades(self, ticker: str | None = None) -> list[TrackedTrade]:
        query = "SELECT * FROM tracked_trades WHERE 1=1"
        params: list[Any] = []
        if ticker is not None:
            query += " AND ticker = ?"
            params.append(ticker)
        conn = self._conn()
        rows = conn.execute(query, params).fetchall()
        return [self._row_to_trade(r) for r in rows]

    def save_trade_outcome(self, outcome: TradeOutcome) -> None:
        conn = self._conn()
        conn.execute(
            """INSERT OR REPLACE INTO trade_outcomes
            (ticker, buy_trade_id, sell_trade_id, buy_price, sell_price,
             quantity, buy_date, sell_date, holding_days, return_pct,
             return_dollar, signals_at_entry, conviction_at_entry)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                outcome.ticker,
                outcome.buy_trade_id,
                outcome.sell_trade_id,
                outcome.buy_price,
                outcome.sell_price,
                outcome.quantity,
                outcome.buy_date,
                outcome.sell_date,
                outcome.holding_days,
                outcome.return_pct,
                outcome.return_dollar,
                json.dumps(outcome.signals_at_entry),
                outcome.conviction_at_entry,
            ),
        )
        conn.commit()

    def get_trade_outcomes(self, ticker: str | None = None) -> list[TradeOutcome]:
        query = "SELECT * FROM trade_outcomes WHERE 1=1"
        params: list[Any] = []
        if ticker is not None:
            query += " AND ticker = ?"
            params.append(ticker)
        conn = self._conn()
        rows = conn.execute(query, params).fetchall()
        return [self._row_to_outcome(r) for r in rows]

    def _row_to_trade(self, r: sqlite3.Row) -> TrackedTrade:
        return TrackedTrade(
            trade_id=r["trade_id"],
            ticker=r["ticker"],
            action=TradeAction(r["action"]),
            price=r["price"],
            quantity=r["quantity"],
            trade_date=r["trade_date"],
            conviction_at_trade=r["conviction_at_trade"],
            signals_at_trade=json.loads(r["signals_at_trade"] or "[]"),
            opportunity_card_id=r["opportunity_card_id"] or "",
            notes=r["notes"] or "",
        )

    def _row_to_outcome(self, r: sqlite3.Row) -> TradeOutcome:
        return TradeOutcome(
            ticker=r["ticker"],
            buy_trade_id=r["buy_trade_id"],
            sell_trade_id=r["sell_trade_id"],
            buy_price=r["buy_price"],
            sell_price=r["sell_price"],
            quantity=r["quantity"],
            buy_date=r["buy_date"],
            sell_date=r["sell_date"],
            holding_days=r["holding_days"],
            return_pct=r["return_pct"],
            return_dollar=r["return_dollar"],
            signals_at_entry=json.loads(r["signals_at_entry"] or "[]"),
            conviction_at_entry=r["conviction_at_entry"],
        )
