"""Weekly corroboration snapshots — mandatory for forward Hypothesis #9 (spec §8)."""

from __future__ import annotations

import sqlite3
from datetime import date

from domain.corroboration_models import ConvergenceTier, HarvestedClaim, Stance
from domain.screened_row import CorroborationSnapshot


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

    def get_snapshots(
        self, as_of: date, window_days: int = 7
    ) -> list[CorroborationSnapshot]:
        """Return CorroborationSnapshot per ticker from most recent run within window_days of as_of."""
        rows = self._c.execute(
            "SELECT id, as_of FROM corroboration_runs ORDER BY as_of DESC"
        ).fetchall()

        run_id: int | None = None
        run_date: date | None = None
        for row in rows:
            candidate_date = date.fromisoformat(row[1])
            if abs((as_of - candidate_date).days) <= window_days:
                run_id = int(row[0])
                run_date = candidate_date
                break

        if run_id is None or run_date is None:
            return []

        claims = self.load_run(run_id)
        return _claims_to_snapshots(claims, run_date)


def _claims_to_snapshots(
    claims: list[HarvestedClaim], run_date: date
) -> list[CorroborationSnapshot]:
    from collections import defaultdict

    by_ticker: dict[str, list[HarvestedClaim]] = defaultdict(list)
    for c in claims:
        if c.verified:
            by_ticker[c.ticker].append(c)

    snapshots: list[CorroborationSnapshot] = []
    for ticker, verified_claims in by_ticker.items():
        bullish = sum(1 for c in verified_claims if c.stance == Stance.BULLISH)
        bearish = sum(1 for c in verified_claims if c.stance == Stance.BEARISH)
        if bullish > 0 and bearish > 0:
            tier = ConvergenceTier.CONFLICTED
        elif bullish >= 3:
            tier = ConvergenceTier.STRONG
        elif bullish == 2:
            tier = ConvergenceTier.MODERATE
        elif bullish == 1:
            tier = ConvergenceTier.WEAK
        else:
            tier = ConvergenceTier.NONE
        snapshots.append(
            CorroborationSnapshot(
                ticker=ticker,
                convergence_tier=tier,
                n_sources=len(verified_claims),
                surfaced_at=run_date,
            )
        )
    return snapshots
