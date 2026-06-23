"""Scan candidates mixin for SQLiteStore."""

from __future__ import annotations

import json
import sqlite3
from typing import Any

from adapters.data.store._base import connect_and_init


class CandidatesMixin:
    _db_path: str

    def _conn(self) -> sqlite3.Connection:
        return connect_and_init(self._db_path)

    def save_scan_candidate(
        self,
        scan_date: str,
        ticker: str,
        conviction: float,
        divergence: float,
        sub_scores: dict[str, float],
        surfaced: bool,
        theme: str | None,
        cap_tier: str | None,
    ) -> None:
        conn = self._conn()
        conn.execute(
            "INSERT INTO scan_candidates "
            "(scan_date, ticker, conviction, divergence, sub_scores_json, surfaced, theme, cap_tier) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (
                scan_date,
                ticker,
                conviction,
                divergence,
                json.dumps(sub_scores),
                1 if surfaced else 0,
                theme,
                cap_tier,
            ),
        )
        conn.commit()

    def get_scan_candidates(self, scan_date: str | None = None) -> list[dict[str, Any]]:
        q = "SELECT * FROM scan_candidates"
        params: list[Any] = []
        if scan_date is not None:
            q += " WHERE scan_date = ?"
            params.append(scan_date)
        q += " ORDER BY conviction DESC"
        conn = self._conn()
        rows = conn.execute(q, params).fetchall()
        out: list[dict[str, Any]] = []
        for r in rows:
            d = dict(r)
            d["sub_scores"] = json.loads(d.pop("sub_scores_json"))
            out.append(d)
        return out
