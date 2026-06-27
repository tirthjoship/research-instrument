"""Surfaced calls and call outcomes mixin for SQLiteStore."""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timedelta

from adapters.data.store._base import connect_and_init
from domain.surfaced_call import (
    CallOutcome,
    EvidenceItem,
    Horizon,
    OpportunityDirection,
    SurfacedCall,
)


class CallsMixin:
    _db_path: str

    def _conn(self) -> sqlite3.Connection:
        return connect_and_init(self._db_path)

    def save_call(self, call: SurfacedCall) -> None:
        conn = self._conn()
        conn.execute(
            """INSERT OR REPLACE INTO surfaced_calls
            (call_id, ticker, surfaced_at, conviction, divergence_score, direction,
             evidence, theme, cap_tier, spy_at_surface, ndx_at_surface)
            VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
            (
                call.call_id,
                call.ticker,
                call.surfaced_at.isoformat(),
                call.conviction,
                call.divergence_score,
                call.direction.value,
                json.dumps([[e.dimension, e.score, e.note] for e in call.evidence]),
                call.theme,
                call.cap_tier,
                call.spy_at_surface,
                call.ndx_at_surface,
            ),
        )
        conn.commit()

    def _row_to_call(self, r: sqlite3.Row) -> SurfacedCall:
        return SurfacedCall(
            call_id=r["call_id"],
            ticker=r["ticker"],
            surfaced_at=datetime.fromisoformat(r["surfaced_at"]),
            conviction=r["conviction"],
            divergence_score=r["divergence_score"],
            direction=OpportunityDirection(r["direction"]),
            evidence=tuple(
                EvidenceItem(d, s, n) for d, s, n in json.loads(r["evidence"])
            ),
            theme=r["theme"],
            cap_tier=r["cap_tier"],
            spy_at_surface=r["spy_at_surface"],
            ndx_at_surface=r["ndx_at_surface"],
        )

    def get_call(self, call_id: str) -> SurfacedCall | None:
        conn = self._conn()
        row = conn.execute(
            "SELECT * FROM surfaced_calls WHERE call_id = ?", (call_id,)
        ).fetchone()
        return self._row_to_call(row) if row else None

    def get_all_calls(self) -> list[SurfacedCall]:
        conn = self._conn()
        rows = conn.execute("SELECT * FROM surfaced_calls").fetchall()
        return [self._row_to_call(r) for r in rows]

    def get_due_calls(self, now: datetime) -> list[tuple[SurfacedCall, Horizon]]:
        conn = self._conn()
        resolved = {
            (r["call_id"], r["horizon"])
            for r in conn.execute(
                "SELECT call_id, horizon FROM call_outcomes"
            ).fetchall()
        }
        due: list[tuple[SurfacedCall, Horizon]] = []
        for call in self.get_all_calls():
            for h in Horizon:
                if (call.call_id, h.value) in resolved:
                    continue
                if now >= call.surfaced_at + timedelta(days=h.value):
                    due.append((call, h))
        return due

    def save_outcome(self, outcome: CallOutcome) -> None:
        conn = self._conn()
        conn.execute(
            """INSERT OR REPLACE INTO call_outcomes
            (call_id, horizon, resolved_at, entry_price, exit_price, forward_return,
             spy_return, ndx_return, beat_spy, beat_ndx, beat_both)
            VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
            (
                outcome.call_id,
                outcome.horizon.value,
                outcome.resolved_at.isoformat(),
                outcome.entry_price,
                outcome.exit_price,
                outcome.forward_return,
                outcome.spy_return,
                outcome.ndx_return,
                int(outcome.beat_spy),
                int(outcome.beat_ndx),
                int(outcome.beat_both),
            ),
        )
        conn.commit()

    def get_outcomes(self) -> list[CallOutcome]:
        conn = self._conn()
        rows = conn.execute("SELECT * FROM call_outcomes").fetchall()
        return [
            CallOutcome(
                call_id=r["call_id"],
                horizon=Horizon(r["horizon"]),
                resolved_at=datetime.fromisoformat(r["resolved_at"]),
                entry_price=r["entry_price"],
                exit_price=r["exit_price"],
                forward_return=r["forward_return"],
                spy_return=r["spy_return"],
                ndx_return=r["ndx_return"],
                beat_spy=bool(r["beat_spy"]),
                beat_ndx=bool(r["beat_ndx"]),
                beat_both=bool(r["beat_both"]),
            )
            for r in rows
        ]
