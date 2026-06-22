"""Weekly corroboration snapshots — mandatory for forward Hypothesis #9 (spec §8)."""

from __future__ import annotations

import sqlite3
from datetime import date

from domain.corroboration_models import HarvestedClaim, Stance


class CorroborationStore:
    def __init__(self, conn: sqlite3.Connection):
        self._c = conn

    def init_schema(self) -> None:
        self._c.executescript(
            """
            CREATE TABLE IF NOT EXISTS corroboration_runs (
                id INTEGER PRIMARY KEY AUTOINCREMENT, as_of TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS harvested_recs (
                run_id INTEGER, source_name TEXT, ticker TEXT, stance TEXT,
                thesis TEXT, url TEXT, published_at TEXT, verified INTEGER,
                reliability_weight REAL);
            """
        )
        self._c.commit()

    def save_run(self, as_of: date, claims: list[HarvestedClaim]) -> int:
        cur = self._c.execute(
            "INSERT INTO corroboration_runs (as_of) VALUES (?)",
            (as_of.isoformat(),),
        )
        assert cur.lastrowid is not None
        run_id = int(cur.lastrowid)
        self._c.executemany(
            "INSERT INTO harvested_recs VALUES (?,?,?,?,?,?,?,?,?)",
            [
                (
                    run_id,
                    c.source_name,
                    c.ticker,
                    c.stance.value,
                    c.thesis_summary,
                    c.url,
                    c.published_at.isoformat(),
                    int(c.verified),
                    c.reliability_weight,
                )
                for c in claims
            ],
        )
        self._c.commit()
        return run_id

    def load_run(self, run_id: int) -> list[HarvestedClaim]:
        rows = self._c.execute(
            "SELECT source_name, ticker, stance, thesis, url, published_at, verified, "
            "reliability_weight FROM harvested_recs WHERE run_id=?",
            (run_id,),
        ).fetchall()
        return [
            HarvestedClaim(
                r[0],
                r[1],
                Stance(r[2]),
                r[3],
                r[4],
                date.fromisoformat(r[5]),
                bool(r[6]),
                r[7],
            )
            for r in rows
        ]
