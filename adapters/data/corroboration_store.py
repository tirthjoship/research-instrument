"""Weekly corroboration snapshots — mandatory for forward Hypothesis #9 (spec §8)."""

from __future__ import annotations

import sqlite3
from datetime import date, timedelta

from domain.corroboration_models import (
    CandidateSnapshot,
    ConvergenceTier,
    DiscoveredEntry,
    HarvestedClaim,
    Stance,
)
from domain.screened_row import CorroborationSnapshot


class CorroborationStore:
    def __init__(self, conn: sqlite3.Connection):
        self._c = conn

    def init_schema(self) -> None:
        self._c.executescript(
            """
            CREATE TABLE IF NOT EXISTS corroboration_runs (
                id    INTEGER PRIMARY KEY AUTOINCREMENT,
                as_of TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS harvested_recs (
                run_id           INTEGER,
                source_name      TEXT,
                ticker           TEXT,
                stance           TEXT,
                thesis           TEXT,
                url              TEXT,
                published_at     TEXT,
                verified         INTEGER,
                reliability_weight REAL
            );
            CREATE TABLE IF NOT EXISTS candidates_snapshot (
                run_id           INTEGER NOT NULL,
                ticker           TEXT NOT NULL,
                convergence      TEXT NOT NULL,
                verification     TEXT NOT NULL,
                mean_convergence REAL NOT NULL,
                PRIMARY KEY (run_id, ticker)
            );
            CREATE TABLE IF NOT EXISTS discovered_tickers (
                ticker       TEXT PRIMARY KEY,
                company_name TEXT,
                sector       TEXT,
                first_seen   TEXT NOT NULL,
                last_seen    TEXT NOT NULL,
                convergence  TEXT NOT NULL,
                run_id       INTEGER
            );
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
            if 0 <= (as_of - candidate_date).days <= window_days:
                run_id = int(row[0])
                run_date = candidate_date
                break

        if run_id is None or run_date is None:
            return []

        claims = self.load_run(run_id)
        return _claims_to_snapshots(claims, run_date)

    # ------------------------------------------------------------------
    # candidates_snapshot
    # ------------------------------------------------------------------

    def save_candidates(self, run_id: int, snaps: list[CandidateSnapshot]) -> None:
        """Persist lightweight candidate projections for a run."""
        self._c.executemany(
            "INSERT OR REPLACE INTO candidates_snapshot VALUES (?,?,?,?,?)",
            [
                (
                    run_id,
                    s.ticker,
                    s.convergence.value,
                    s.verification,
                    s.mean_convergence,
                )
                for s in snaps
            ],
        )
        self._c.commit()

    def load_candidates(self, run_id: int) -> list[CandidateSnapshot]:
        """Load candidate snapshots for a past run. Returns [] if run unknown."""
        rows = self._c.execute(
            "SELECT ticker, convergence, verification, mean_convergence "
            "FROM candidates_snapshot WHERE run_id=?",
            (run_id,),
        ).fetchall()
        return [
            CandidateSnapshot(r[0], ConvergenceTier(r[1]), r[2], r[3]) for r in rows
        ]

    def latest_run_id(self) -> int | None:
        """Return the id of the most recent corroboration run, or None if empty."""
        row = self._c.execute(
            "SELECT id FROM corroboration_runs ORDER BY id DESC LIMIT 1"
        ).fetchone()
        return int(row[0]) if row else None

    # ------------------------------------------------------------------
    # discovered_tickers
    # ------------------------------------------------------------------

    def upsert_discovered(
        self,
        ticker: str,
        company_name: str,
        sector: str,
        as_of: date,
        convergence: ConvergenceTier,
        run_id: int,
    ) -> None:
        """Insert ticker or update last_seen/convergence/run_id on repeat appearance."""
        existing = self._c.execute(
            "SELECT first_seen FROM discovered_tickers WHERE ticker=?", (ticker,)
        ).fetchone()
        first_seen = existing[0] if existing else as_of.isoformat()
        self._c.execute(
            """
            INSERT INTO discovered_tickers
                (ticker, company_name, sector, first_seen, last_seen, convergence, run_id)
            VALUES (?,?,?,?,?,?,?)
            ON CONFLICT(ticker) DO UPDATE SET
                last_seen=excluded.last_seen,
                convergence=excluded.convergence,
                run_id=excluded.run_id
            """,
            (
                ticker,
                company_name,
                sector,
                first_seen,
                as_of.isoformat(),
                convergence.value,
                run_id,
            ),
        )
        self._c.commit()

    def active_discovered(
        self, as_of: date, dry_weeks: int = 2
    ) -> list[DiscoveredEntry]:
        """Return tickers whose last_seen >= as_of - dry_weeks*7 days."""
        cutoff = (as_of - timedelta(weeks=dry_weeks)).isoformat()
        rows = self._c.execute(
            "SELECT ticker, company_name, sector, first_seen, last_seen, convergence "
            "FROM discovered_tickers WHERE last_seen >= ?",
            (cutoff,),
        ).fetchall()
        return [
            DiscoveredEntry(
                ticker=r[0],
                company_name=r[1] or "",
                sector=r[2] or "unknown",
                first_seen=date.fromisoformat(r[3]),
                last_seen=date.fromisoformat(r[4]),
                convergence=ConvergenceTier(r[5]),
            )
            for r in rows
        ]

    def expire_discovered(self, as_of: date, dry_weeks: int = 2) -> int:
        """Delete tickers not seen in dry_weeks. Returns count removed."""
        cutoff = (as_of - timedelta(weeks=dry_weeks)).isoformat()
        cur = self._c.execute(
            "DELETE FROM discovered_tickers WHERE last_seen < ?", (cutoff,)
        )
        self._c.commit()
        return cur.rowcount


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
