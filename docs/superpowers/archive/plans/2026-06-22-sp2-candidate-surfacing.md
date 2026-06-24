# SP2 Candidate Surfacing Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Let new tickers (outside the static ~120-ticker universe) enter the scoring pipeline when the weekly corroboration engine flags them at STRONG/MODERATE convergence with ALL_VERIFIED citations.

**Architecture:** `SurfacingUseCase` reads `CandidateSnapshot` objects from `CorroborationStore`, applies admission logic (convergence tier + verification + de-dup against spine), resolves ticker metadata via yfinance, and writes to a `discovered_tickers` table. `HybridUniverseProvider` reads active discovered tickers as a third overlay source. A `surface-candidates` CLI command wires everything together.

**Tech Stack:** Python 3.12+, SQLite (stdlib sqlite3), yfinance, click, loguru, pytest, in-memory SQLite for tests.

**Worktree:** `/Users/tirthjoshi/My Data Science Projects/ML_Portfolio_Projects/corroboration-sp7`
**Branch:** `feat/corroboration-engine`
**Run all commands from worktree root.**

---

## File Map

| File | Action | What changes |
|---|---|---|
| `domain/corroboration_models.py` | Modify | Add `CandidateSnapshot`, `DiscoveredEntry` dataclasses |
| `domain/ports.py` | Modify | Add `TickerResolverPort` protocol |
| `adapters/data/corroboration_store.py` | Modify | Add `candidates_snapshot` table, `discovered_tickers` table, 5 new methods |
| `application/cli/corroboration_commands.py` | Modify | Call `store.save_candidates()` after `uc.execute()` |
| `adapters/data/yfinance_resolver.py` | Create | Thin yfinance adapter implementing `TickerResolverPort` |
| `application/surfacing_use_case.py` | Create | Admission logic use case |
| `adapters/data/hybrid_universe_provider.py` | Modify | Add `_corroboration_overlay()`, optional `store` param |
| `application/cli/scan_commands.py` | Modify | Add `surface-candidates` command |
| `tests/test_surfacing_use_case.py` | Create | 11 tests, in-memory SQLite + `FakeTickerResolver` |

---

## Task 1: Add `CandidateSnapshot` and `DiscoveredEntry` to domain models

**Files:**
- Modify: `domain/corroboration_models.py`

- [ ] **Step 1: Write the failing test**

Create `tests/test_corroboration_models_sp2.py`:

```python
from datetime import date
from domain.corroboration_models import (
    CandidateSnapshot,
    ConvergenceTier,
    DiscoveredEntry,
)


def test_candidate_snapshot_fields() -> None:
    snap = CandidateSnapshot(
        ticker="NVDA",
        convergence=ConvergenceTier.STRONG,
        verification="ALL_VERIFIED",
        mean_convergence=0.85,
    )
    assert snap.ticker == "NVDA"
    assert snap.convergence == ConvergenceTier.STRONG
    assert snap.verification == "ALL_VERIFIED"
    assert snap.mean_convergence == 0.85


def test_discovered_entry_fields() -> None:
    entry = DiscoveredEntry(
        ticker="NVDA",
        company_name="NVIDIA Corporation",
        sector="Technology",
        first_seen=date(2026, 6, 22),
        last_seen=date(2026, 6, 22),
        convergence=ConvergenceTier.STRONG,
    )
    assert entry.ticker == "NVDA"
    assert entry.sector == "Technology"
    assert entry.convergence == ConvergenceTier.STRONG
```

- [ ] **Step 2: Run test to verify it fails**

```bash
pytest tests/test_corroboration_models_sp2.py -q
```

Expected: `ImportError: cannot import name 'CandidateSnapshot'`

- [ ] **Step 3: Add dataclasses to `domain/corroboration_models.py`**

Open `domain/corroboration_models.py`. After the existing `@dataclass` definitions (after `class CorroboratedCandidate`), add:

```python
@dataclass(frozen=True)
class CandidateSnapshot:
    """Lightweight projection of CorroboratedCandidate for persistence and surfacing."""

    ticker: str
    convergence: ConvergenceTier
    verification: str  # "ALL_VERIFIED" | "PARTIAL" | "NONE_DROPPED"
    mean_convergence: float  # 0-1


@dataclass(frozen=True)
class DiscoveredEntry:
    """A ticker admitted to the corroboration overlay universe."""

    ticker: str
    company_name: str
    sector: str
    first_seen: date
    last_seen: date
    convergence: ConvergenceTier
```

- [ ] **Step 4: Run test to verify it passes**

```bash
pytest tests/test_corroboration_models_sp2.py -q
```

Expected: `2 passed`

- [ ] **Step 5: Run domain tests to check for regressions**

```bash
make test-domain
```

Expected: all domain tests pass.

- [ ] **Step 6: Commit**

```bash
git add domain/corroboration_models.py tests/test_corroboration_models_sp2.py
git commit -m "feat(domain): add CandidateSnapshot and DiscoveredEntry dataclasses for SP2"
```

---

## Task 2: Add `TickerResolverPort` to `domain/ports.py`

**Files:**
- Modify: `domain/ports.py`

- [ ] **Step 1: Write the failing test**

Add to `tests/test_corroboration_models_sp2.py`:

```python
from domain.ports import TickerResolverPort


def test_ticker_resolver_port_is_protocol() -> None:
    import typing

    assert hasattr(TickerResolverPort, "__protocol_attrs__") or (
        typing.get_origin(TickerResolverPort) is not None
        or hasattr(TickerResolverPort, "_is_protocol")
    )


class _FakeResolver:
    def resolve(self, ticker: str) -> tuple[str, str]:
        return ("Fake Corp", "Technology")


def test_fake_resolver_satisfies_port() -> None:
    resolver: TickerResolverPort = _FakeResolver()  # type: ignore[assignment]
    name, sector = resolver.resolve("NVDA")
    assert name == "Fake Corp"
    assert sector == "Technology"
```

- [ ] **Step 2: Run test to verify it fails**

```bash
pytest tests/test_corroboration_models_sp2.py::test_ticker_resolver_port_is_protocol -q
```

Expected: `ImportError: cannot import name 'TickerResolverPort'`

- [ ] **Step 3: Add `TickerResolverPort` to `domain/ports.py`**

Open `domain/ports.py`. At the bottom (before any closing lines), add:

```python
class TickerResolverPort(Protocol):
    """Port: resolve a ticker symbol to company metadata."""

    def resolve(self, ticker: str) -> tuple[str, str]:
        """Return (company_name, sector). Never raises — returns ("", "unknown") on failure."""
        ...
```

- [ ] **Step 4: Run test to verify it passes**

```bash
pytest tests/test_corroboration_models_sp2.py -q
```

Expected: `4 passed`

- [ ] **Step 5: Run mypy to verify no type errors**

```bash
make typecheck
```

Expected: `Success: no issues found`

- [ ] **Step 6: Commit**

```bash
git add domain/ports.py tests/test_corroboration_models_sp2.py
git commit -m "feat(domain): add TickerResolverPort protocol for SP2"
```

---

## Task 3: Extend `CorroborationStore` — two new tables and five new methods

**Files:**
- Modify: `adapters/data/corroboration_store.py`
- Create: `tests/test_corroboration_store_sp2.py`

This task adds:
- `candidates_snapshot` table + `save_candidates()` / `load_candidates()`
- `discovered_tickers` table + `upsert_discovered()` / `active_discovered()` / `expire_discovered()`

- [ ] **Step 1: Write all failing tests**

Create `tests/test_corroboration_store_sp2.py`:

```python
"""Tests for CorroborationStore SP2 additions (in-memory SQLite)."""
from __future__ import annotations

import sqlite3
from datetime import date

import pytest

from adapters.data.corroboration_store import CorroborationStore
from domain.corroboration_models import (
    CandidateSnapshot,
    ConvergenceTier,
    DiscoveredEntry,
)


@pytest.fixture()
def store() -> CorroborationStore:
    conn = sqlite3.connect(":memory:")
    s = CorroborationStore(conn)
    s.init_schema()
    return s


# ---- candidates_snapshot ----

def test_save_and_load_candidates(store: CorroborationStore) -> None:
    run_id = store.save_run(date(2026, 6, 22), [])
    snaps = [
        CandidateSnapshot("NVDA", ConvergenceTier.STRONG, "ALL_VERIFIED", 0.9),
        CandidateSnapshot("PANW", ConvergenceTier.MODERATE, "ALL_VERIFIED", 0.6),
    ]
    store.save_candidates(run_id, snaps)
    loaded = store.load_candidates(run_id)
    assert len(loaded) == 2
    assert loaded[0].ticker == "NVDA"
    assert loaded[0].convergence == ConvergenceTier.STRONG
    assert loaded[1].ticker == "PANW"
    assert loaded[1].mean_convergence == pytest.approx(0.6)


def test_load_candidates_empty_run(store: CorroborationStore) -> None:
    run_id = store.save_run(date(2026, 6, 22), [])
    assert store.load_candidates(run_id) == []


def test_load_candidates_unknown_run(store: CorroborationStore) -> None:
    assert store.load_candidates(9999) == []


# ---- discovered_tickers ----

def test_upsert_and_active_discovered(store: CorroborationStore) -> None:
    as_of = date(2026, 6, 22)
    store.upsert_discovered("NVDA", "NVIDIA", "Technology", as_of, ConvergenceTier.STRONG, run_id=1)
    active = store.active_discovered(as_of)
    assert len(active) == 1
    e = active[0]
    assert e.ticker == "NVDA"
    assert e.company_name == "NVIDIA"
    assert e.sector == "Technology"
    assert e.convergence == ConvergenceTier.STRONG
    assert e.first_seen == as_of
    assert e.last_seen == as_of


def test_upsert_updates_last_seen(store: CorroborationStore) -> None:
    store.upsert_discovered("NVDA", "NVIDIA", "Technology", date(2026, 6, 8), ConvergenceTier.MODERATE, run_id=1)
    store.upsert_discovered("NVDA", "NVIDIA", "Technology", date(2026, 6, 22), ConvergenceTier.STRONG, run_id=2)
    active = store.active_discovered(date(2026, 6, 22))
    assert len(active) == 1
    assert active[0].first_seen == date(2026, 6, 8)   # preserved
    assert active[0].last_seen == date(2026, 6, 22)   # updated
    assert active[0].convergence == ConvergenceTier.STRONG  # updated


def test_active_discovered_excludes_stale(store: CorroborationStore) -> None:
    store.upsert_discovered("STALE", "Stale Corp", "Finance", date(2026, 6, 1), ConvergenceTier.MODERATE, run_id=1)
    active = store.active_discovered(date(2026, 6, 22), dry_weeks=2)
    assert not any(e.ticker == "STALE" for e in active)


def test_expire_discovered_removes_stale(store: CorroborationStore) -> None:
    store.upsert_discovered("OLD", "Old Corp", "Energy", date(2026, 6, 1), ConvergenceTier.MODERATE, run_id=1)
    store.upsert_discovered("NEW", "New Corp", "Tech", date(2026, 6, 22), ConvergenceTier.STRONG, run_id=2)
    removed = store.expire_discovered(date(2026, 6, 22), dry_weeks=2)
    assert removed == 1
    active = store.active_discovered(date(2026, 6, 22))
    assert len(active) == 1
    assert active[0].ticker == "NEW"


def test_latest_run_id_returns_none_when_empty(store: CorroborationStore) -> None:
    assert store.latest_run_id() is None


def test_latest_run_id_returns_most_recent(store: CorroborationStore) -> None:
    r1 = store.save_run(date(2026, 6, 15), [])
    r2 = store.save_run(date(2026, 6, 22), [])
    assert store.latest_run_id() == r2
    assert r2 > r1
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
pytest tests/test_corroboration_store_sp2.py -q
```

Expected: Multiple failures — methods don't exist yet.

- [ ] **Step 3: Add new tables and methods to `adapters/data/corroboration_store.py`**

Open `adapters/data/corroboration_store.py`. Make the following changes:

**3a — update imports at top of file:**

```python
from __future__ import annotations

import json
import sqlite3
from datetime import date, timedelta

from domain.corroboration_models import (
    CandidateSnapshot,
    ConvergenceTier,
    DiscoveredEntry,
    HarvestedClaim,
    Stance,
)
```

**3b — extend `init_schema()` with two new tables (add inside the `executescript` string, after the existing table definitions):**

```python
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
```

**3c — add five new methods after the existing `load_run()` method:**

```python
    # ------------------------------------------------------------------
    # candidates_snapshot — persist CorroboratedCandidate projections
    # ------------------------------------------------------------------

    def save_candidates(self, run_id: int, snaps: list[CandidateSnapshot]) -> None:
        """Persist lightweight candidate projections for a run."""
        self._c.executemany(
            "INSERT OR REPLACE INTO candidates_snapshot VALUES (?,?,?,?,?)",
            [
                (run_id, s.ticker, s.convergence.value, s.verification, s.mean_convergence)
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
            CandidateSnapshot(r[0], ConvergenceTier(r[1]), r[2], r[3])
            for r in rows
        ]

    def latest_run_id(self) -> int | None:
        """Return the id of the most recent corroboration run, or None if empty."""
        row = self._c.execute(
            "SELECT id FROM corroboration_runs ORDER BY id DESC LIMIT 1"
        ).fetchone()
        return int(row[0]) if row else None

    # ------------------------------------------------------------------
    # discovered_tickers — corroboration universe overlay
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
            (ticker, company_name, sector, first_seen, as_of.isoformat(), convergence.value, run_id),
        )
        self._c.commit()

    def active_discovered(self, as_of: date, dry_weeks: int = 2) -> list[DiscoveredEntry]:
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
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
pytest tests/test_corroboration_store_sp2.py -q
```

Expected: `9 passed`

- [ ] **Step 5: Run adapter tests for regressions**

```bash
make test-adapters
```

Expected: all pass.

- [ ] **Step 6: Commit**

```bash
git add adapters/data/corroboration_store.py tests/test_corroboration_store_sp2.py
git commit -m "feat(adapters): extend CorroborationStore with candidate snapshots and discovered_tickers table"
```

---

## Task 4: Update `corroborate` CLI to save candidate snapshots

**Files:**
- Modify: `application/cli/corroboration_commands.py`

- [ ] **Step 1: Locate the `result = uc.execute(as_of)` line in `corroborate()`**

In `application/cli/corroboration_commands.py`, find:

```python
    result = uc.execute(as_of)
    click.echo(f"Run ID: {result.run_id}  |  candidates: {len(result.candidates)}\n")
```

- [ ] **Step 2: Add snapshot save immediately after that block**

Replace those two lines with:

```python
    result = uc.execute(as_of)
    click.echo(f"Run ID: {result.run_id}  |  candidates: {len(result.candidates)}\n")

    # Persist lightweight snapshots so surface-candidates can load past runs.
    from domain.corroboration_models import CandidateSnapshot

    snaps = [
        CandidateSnapshot(
            ticker=c.ticker,
            convergence=c.convergence,
            verification=c.verification,
            mean_convergence=c.mean_convergence,
        )
        for c in result.candidates
    ]
    store.save_candidates(result.run_id, snaps)
```

- [ ] **Step 3: Run the corroboration CLI smoke-test (dry — no network)**

```bash
python -m application.cli corroborate --help
```

Expected: help text prints without import errors.

- [ ] **Step 4: Run mypy**

```bash
make typecheck
```

Expected: `Success: no issues found`

- [ ] **Step 5: Commit**

```bash
git add application/cli/corroboration_commands.py
git commit -m "feat(cli): save CandidateSnapshot after each corroborate run for SP2 surfacing"
```

---

## Task 5: Create `YFinanceResolver` adapter

**Files:**
- Create: `adapters/data/yfinance_resolver.py`

- [ ] **Step 1: Write the failing test**

Add to `tests/test_corroboration_store_sp2.py` (or a new file — append here for brevity):

```python
# ---- YFinanceResolver (uses a fake yfinance via monkeypatch) ----

def test_yfinance_resolver_returns_name_and_sector(monkeypatch: pytest.MonkeyPatch) -> None:
    from adapters.data.yfinance_resolver import YFinanceResolver

    class _FakeTicker:
        info = {"longName": "NVIDIA Corporation", "sector": "Technology"}

    monkeypatch.setattr("yfinance.Ticker", lambda _: _FakeTicker())
    resolver = YFinanceResolver()
    name, sector = resolver.resolve("NVDA")
    assert name == "NVIDIA Corporation"
    assert sector == "Technology"


def test_yfinance_resolver_returns_empty_on_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    from adapters.data.yfinance_resolver import YFinanceResolver

    monkeypatch.setattr("yfinance.Ticker", lambda _: (_ for _ in ()).throw(RuntimeError("rate limit")))
    resolver = YFinanceResolver()
    name, sector = resolver.resolve("FAKE")
    assert name == ""
    assert sector == "unknown"
```

- [ ] **Step 2: Run test to verify it fails**

```bash
pytest tests/test_corroboration_store_sp2.py::test_yfinance_resolver_returns_name_and_sector -q
```

Expected: `ImportError: No module named 'adapters.data.yfinance_resolver'`

- [ ] **Step 3: Create `adapters/data/yfinance_resolver.py`**

```python
"""YFinance adapter for TickerResolverPort — resolves ticker → (company_name, sector)."""
from __future__ import annotations

from loguru import logger


class YFinanceResolver:
    """Implements TickerResolverPort via yfinance.Ticker.info."""

    def resolve(self, ticker: str) -> tuple[str, str]:
        """Return (company_name, sector). Returns ("", "unknown") on any failure."""
        try:
            import yfinance as yf

            info = yf.Ticker(ticker).info
            return info.get("longName", ""), info.get("sector", "unknown")
        except Exception as exc:
            logger.debug("[yfinance_resolver] {} failed to resolve: {}", ticker, exc)
            return "", "unknown"
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
pytest tests/test_corroboration_store_sp2.py -q
```

Expected: all pass (including 2 new resolver tests).

- [ ] **Step 5: Commit**

```bash
git add adapters/data/yfinance_resolver.py tests/test_corroboration_store_sp2.py
git commit -m "feat(adapters): add YFinanceResolver implementing TickerResolverPort"
```

---

## Task 6: Create `SurfacingUseCase`

**Files:**
- Create: `application/surfacing_use_case.py`
- Create: `tests/test_surfacing_use_case.py`

- [ ] **Step 1: Write all 11 failing tests**

Create `tests/test_surfacing_use_case.py`:

```python
"""Tests for SurfacingUseCase — in-memory SQLite, FakeTickerResolver, no yfinance."""
from __future__ import annotations

import logging
import sqlite3
from datetime import date

import pytest

from adapters.data.corroboration_store import CorroborationStore
from application.surfacing_use_case import SurfacingUseCase
from domain.corroboration_models import (
    CandidateSnapshot,
    ConvergenceTier,
    DiscoveredEntry,
)


class FakeTickerResolver:
    def __init__(self, mapping: dict[str, tuple[str, str]] | None = None) -> None:
        self._mapping = mapping or {}

    def resolve(self, ticker: str) -> tuple[str, str]:
        return self._mapping.get(ticker, (f"{ticker} Corp", "Unknown"))


@pytest.fixture()
def store() -> CorroborationStore:
    conn = sqlite3.connect(":memory:")
    s = CorroborationStore(conn)
    s.init_schema()
    return s


@pytest.fixture()
def resolver() -> FakeTickerResolver:
    return FakeTickerResolver({"NVDA": ("NVIDIA", "Technology"), "PANW": ("Palo Alto", "Technology")})


def _run(
    store: CorroborationStore,
    resolver: FakeTickerResolver,
    candidates: list[CandidateSnapshot],
    spine: frozenset[str] | None = None,
    max_admissions: int = 10,
    as_of: date | None = None,
) -> list[DiscoveredEntry]:
    uc = SurfacingUseCase(
        store=store,
        spine_tickers=spine or frozenset(),
        resolver=resolver,
        max_admissions=max_admissions,
    )
    return uc.run(candidates=candidates, run_id=1, as_of=as_of or date(2026, 6, 22))


def test_admits_strong_all_verified(store: CorroborationStore, resolver: FakeTickerResolver) -> None:
    candidates = [CandidateSnapshot("NVDA", ConvergenceTier.STRONG, "ALL_VERIFIED", 0.9)]
    result = _run(store, resolver, candidates)
    assert len(result) == 1
    assert result[0].ticker == "NVDA"


def test_admits_moderate_all_verified(store: CorroborationStore, resolver: FakeTickerResolver) -> None:
    candidates = [CandidateSnapshot("PANW", ConvergenceTier.MODERATE, "ALL_VERIFIED", 0.6)]
    result = _run(store, resolver, candidates)
    assert len(result) == 1
    assert result[0].ticker == "PANW"


def test_rejects_weak(store: CorroborationStore, resolver: FakeTickerResolver) -> None:
    candidates = [CandidateSnapshot("WEAK", ConvergenceTier.WEAK, "ALL_VERIFIED", 0.2)]
    result = _run(store, resolver, candidates)
    assert result == []


def test_rejects_partial_verification(store: CorroborationStore, resolver: FakeTickerResolver) -> None:
    candidates = [CandidateSnapshot("NVDA", ConvergenceTier.STRONG, "PARTIAL", 0.9)]
    result = _run(store, resolver, candidates)
    assert result == []


def test_dedup_spine(
    store: CorroborationStore,
    resolver: FakeTickerResolver,
    caplog: pytest.LogCaptureFixture,
) -> None:
    candidates = [CandidateSnapshot("NVDA", ConvergenceTier.STRONG, "ALL_VERIFIED", 0.9)]
    with caplog.at_level(logging.DEBUG):
        result = _run(store, resolver, candidates, spine=frozenset({"NVDA"}))
    assert result == []
    assert any("spine" in r.message.lower() for r in caplog.records)


def test_cap_at_max_admissions(store: CorroborationStore) -> None:
    resolver = FakeTickerResolver()
    candidates = [
        CandidateSnapshot(f"T{i:02d}", ConvergenceTier.STRONG, "ALL_VERIFIED", 0.9 - i * 0.01)
        for i in range(15)
    ]
    result = _run(store, resolver, candidates, max_admissions=10)
    assert len(result) == 10
    # highest mean_convergence admitted first
    assert result[0].ticker == "T00"


def test_ttl_expire(store: CorroborationStore, resolver: FakeTickerResolver) -> None:
    # Seed a stale ticker directly (last_seen 15 days ago)
    store.upsert_discovered(
        "OLD", "Old Corp", "Finance", date(2026, 6, 7), ConvergenceTier.MODERATE, run_id=0
    )
    # Run surfacing with empty new candidates — expire should remove OLD
    _run(store, resolver, [], as_of=date(2026, 6, 22))
    active = store.active_discovered(date(2026, 6, 22))
    assert not any(e.ticker == "OLD" for e in active)


def test_ttl_refresh(store: CorroborationStore, resolver: FakeTickerResolver) -> None:
    # Ticker was seen 10 days ago (still within TTL)
    store.upsert_discovered(
        "NVDA", "NVIDIA", "Technology", date(2026, 6, 12), ConvergenceTier.MODERATE, run_id=0
    )
    # Appears again now — should update last_seen
    candidates = [CandidateSnapshot("NVDA", ConvergenceTier.STRONG, "ALL_VERIFIED", 0.9)]
    _run(store, resolver, candidates, as_of=date(2026, 6, 22))
    active = store.active_discovered(date(2026, 6, 22))
    nvda = next(e for e in active if e.ticker == "NVDA")
    assert nvda.last_seen == date(2026, 6, 22)
    assert nvda.first_seen == date(2026, 6, 12)  # preserved


def test_resolver_failure_still_admits(store: CorroborationStore) -> None:
    class _FailingResolver:
        def resolve(self, ticker: str) -> tuple[str, str]:
            raise RuntimeError("yfinance down")

    uc = SurfacingUseCase(
        store=store,
        spine_tickers=frozenset(),
        resolver=_FailingResolver(),  # type: ignore[arg-type]
        max_admissions=10,
    )
    candidates = [CandidateSnapshot("NVDA", ConvergenceTier.STRONG, "ALL_VERIFIED", 0.9)]
    result = uc.run(candidates=candidates, run_id=1, as_of=date(2026, 6, 22))
    assert len(result) == 1
    assert result[0].ticker == "NVDA"
    assert result[0].company_name == ""
    assert result[0].sector == "unknown"


def test_hybrid_universe_corroboration_overlay(store: CorroborationStore, resolver: FakeTickerResolver) -> None:
    from unittest.mock import MagicMock

    from adapters.data.hybrid_universe_provider import HybridUniverseProvider
    from datetime import datetime

    # Pre-seed a discovered ticker
    store.upsert_discovered(
        "NVDA", "NVIDIA", "Technology", date(2026, 6, 22), ConvergenceTier.STRONG, run_id=1
    )

    buzz_mock = MagicMock()
    buzz_mock.scan_sources.return_value = []
    provider = HybridUniverseProvider(
        themes_path="config/universe/themes.yaml",
        buzz_discovery=buzz_mock,
        store=store,
    )
    universe = provider.get_universe(datetime(2026, 6, 22))
    tickers = {e.ticker for e in universe}
    assert "NVDA" in tickers
    # Theme for discovered tickers
    nvda_entry = next(e for e in universe if e.ticker == "NVDA")
    assert nvda_entry.theme == "corroboration"


def test_hybrid_universe_dedup_log(
    store: CorroborationStore,
    caplog: pytest.LogCaptureFixture,
) -> None:
    from unittest.mock import MagicMock

    from adapters.data.hybrid_universe_provider import HybridUniverseProvider
    from datetime import datetime

    import yaml
    from pathlib import Path

    # Find a ticker already in themes.yaml
    themes_path = "config/universe/themes.yaml"
    data = yaml.safe_load(Path(themes_path).read_text())
    spine_ticker = next(iter(next(iter(data["themes"].values()))))

    # Seed that same ticker as discovered
    store.upsert_discovered(
        spine_ticker, "Corp", "Tech", date(2026, 6, 22), ConvergenceTier.STRONG, run_id=1
    )

    buzz_mock = MagicMock()
    buzz_mock.scan_sources.return_value = []
    provider = HybridUniverseProvider(
        themes_path=themes_path,
        buzz_discovery=buzz_mock,
        store=store,
    )
    with caplog.at_level(logging.DEBUG):
        universe = provider.get_universe(datetime(2026, 6, 22))

    # Ticker appears only once (not duplicated)
    tickers = [e.ticker for e in universe]
    assert tickers.count(spine_ticker) == 1
    # Debug log fired
    assert any("corroboration overlay" in r.message.lower() for r in caplog.records)
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
pytest tests/test_surfacing_use_case.py -q
```

Expected: `ImportError: No module named 'application.surfacing_use_case'`

- [ ] **Step 3: Create `application/surfacing_use_case.py`**

```python
"""SP2: Candidate Surfacing — admits corroborated tickers into discovered universe overlay."""
from __future__ import annotations

from datetime import date

from loguru import logger

from adapters.data.corroboration_store import CorroborationStore
from domain.corroboration_models import (
    CandidateSnapshot,
    ConvergenceTier,
    DiscoveredEntry,
)
from domain.ports import TickerResolverPort

_ADMIT_TIERS = {ConvergenceTier.STRONG, ConvergenceTier.MODERATE}
_ADMIT_VERIFICATION = "ALL_VERIFIED"


class SurfacingUseCase:
    """Admit corroboration candidates into the discovered-ticker universe overlay."""

    def __init__(
        self,
        store: CorroborationStore,
        spine_tickers: frozenset[str],
        resolver: TickerResolverPort,
        max_admissions: int = 10,
    ) -> None:
        self._store = store
        self._spine = spine_tickers
        self._resolver = resolver
        self._max = max_admissions

    def run(
        self,
        candidates: list[CandidateSnapshot],
        run_id: int,
        as_of: date,
    ) -> list[DiscoveredEntry]:
        """Apply admission logic and update the discovered_tickers table.

        Returns the full active discovered universe after this run.
        """
        eligible = sorted(
            (
                c for c in candidates
                if c.convergence in _ADMIT_TIERS and c.verification == _ADMIT_VERIFICATION
            ),
            key=lambda c: c.mean_convergence,
            reverse=True,
        )

        admitted = 0
        for snap in eligible:
            if admitted >= self._max:
                break
            if snap.ticker in self._spine:
                logger.debug(
                    "[surfacing] {} already in spine, skipping corroboration overlay",
                    snap.ticker,
                )
                continue
            try:
                company_name, sector = self._resolver.resolve(snap.ticker)
            except Exception:
                company_name, sector = "", "unknown"

            self._store.upsert_discovered(
                ticker=snap.ticker,
                company_name=company_name,
                sector=sector,
                as_of=as_of,
                convergence=snap.convergence,
                run_id=run_id,
            )
            admitted += 1
            logger.info("[surfacing] admitted {} ({}) convergence={}", snap.ticker, company_name, snap.convergence.value)

        expired = self._store.expire_discovered(as_of)
        if expired:
            logger.info("[surfacing] expired {} stale ticker(s) from discovered universe", expired)

        return self._store.active_discovered(as_of)
```

- [ ] **Step 4: Run the first 9 tests (use case tests — skip overlay tests for now)**

```bash
pytest tests/test_surfacing_use_case.py -q -k "not hybrid"
```

Expected: `9 passed`

- [ ] **Step 5: Commit the use case before wiring the provider**

```bash
git add application/surfacing_use_case.py tests/test_surfacing_use_case.py
git commit -m "feat(application): add SurfacingUseCase with admission logic and TTL management"
```

---

## Task 7: Extend `HybridUniverseProvider` with corroboration overlay

**Files:**
- Modify: `adapters/data/hybrid_universe_provider.py`

- [ ] **Step 1: Confirm the 2 overlay tests currently fail**

```bash
pytest tests/test_surfacing_use_case.py::test_hybrid_universe_corroboration_overlay tests/test_surfacing_use_case.py::test_hybrid_universe_dedup_log -q
```

Expected: `TypeError` or `unexpected keyword argument 'store'`

- [ ] **Step 2: Modify `adapters/data/hybrid_universe_provider.py`**

Replace the entire file with:

```python
"""Hybrid universe: curated thematic spine + corroboration overlay + buzz discovery."""
from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING

import yaml
from loguru import logger

from domain.ports import BuzzDiscoveryPort
from domain.universe import UniverseEntry

if TYPE_CHECKING:
    from adapters.data.corroboration_store import CorroborationStore


class HybridUniverseProvider:
    def __init__(
        self,
        themes_path: str,
        buzz_discovery: BuzzDiscoveryPort,
        max_discovery: int = 50,
        store: "CorroborationStore | None" = None,
    ) -> None:
        self._themes_path = themes_path
        self._buzz = buzz_discovery
        self._max_discovery = max_discovery
        self._store = store

    def _spine(self) -> dict[str, str]:
        data = yaml.safe_load(Path(self._themes_path).read_text())
        out: dict[str, str] = {}
        for theme, tickers in data.get("themes", {}).items():
            for t in tickers:
                out.setdefault(t, theme)
        return out

    def _corroboration_overlay(self, now: datetime) -> dict[str, str]:
        if self._store is None:
            return {}
        return {
            e.ticker: "corroboration"
            for e in self._store.active_discovered(now.date())
        }

    def get_universe(self, now: datetime) -> list[UniverseEntry]:
        spine = self._spine()
        entries = [UniverseEntry(ticker=t, theme=theme) for t, theme in spine.items()]
        seen = set(spine)

        # Second source: corroboration overlay
        for ticker, theme in self._corroboration_overlay(now).items():
            if ticker in seen:
                logger.debug(
                    "[universe] {} in corroboration overlay but already in spine, skipping",
                    ticker,
                )
                continue
            seen.add(ticker)
            entries.append(UniverseEntry(ticker=ticker, theme=theme))

        # Third source: buzz discovery
        try:
            signals = self._buzz.scan_sources(now)
        except Exception as exc:  # noqa: BLE001
            logger.warning("buzz discovery failed, spine+overlay universe: {}", exc)
            return entries

        added = 0
        for sig in signals:
            t = sig.ticker
            if t in seen or added >= self._max_discovery:
                continue
            seen.add(t)
            entries.append(UniverseEntry(ticker=t, theme="discovery"))
            added += 1
        return entries
```

- [ ] **Step 3: Run all surfacing tests**

```bash
pytest tests/test_surfacing_use_case.py -q
```

Expected: `11 passed`

- [ ] **Step 4: Run full adapter tests for regressions**

```bash
make test-adapters
```

Expected: all pass.

- [ ] **Step 5: Commit**

```bash
git add adapters/data/hybrid_universe_provider.py
git commit -m "feat(adapters): add corroboration overlay as third source in HybridUniverseProvider"
```

---

## Task 8: Add `surface-candidates` CLI command

**Files:**
- Modify: `application/cli/scan_commands.py`

- [ ] **Step 1: Add the command at the bottom of `application/cli/scan_commands.py`**

Open `application/cli/scan_commands.py`. Add these imports at the top with existing imports:

```python
from datetime import date as _date, datetime, timedelta
```

(If `datetime` is already imported, skip it — only add `date as _date` and `timedelta` if missing.)

Then append the new command at the bottom of the file:

```python
@cli.command("surface-candidates")
@click.option("--run-id", default=None, type=int, help="Corroboration run ID to read (default: latest)")
@click.option("--date", "as_of_str", default=None, help="As-of date YYYY-MM-DD for TTL (default: today UTC)")
@click.option("--max", "max_admissions", default=10, show_default=True, type=int, help="Max tickers to admit this run")
@click.option("--dry-run", is_flag=True, default=False, help="Print admissions without writing to store")
def surface_candidates(
    run_id: int | None,
    as_of_str: str | None,
    max_admissions: int,
    dry_run: bool,
) -> None:
    """Surface corroborated tickers into the discovered-universe overlay. RESEARCH_ONLY."""
    import sqlite3
    from pathlib import Path

    import yaml

    from adapters.data.corroboration_store import CorroborationStore
    from adapters.data.yfinance_resolver import YFinanceResolver
    from application.surfacing_use_case import SurfacingUseCase

    as_of = _date.fromisoformat(as_of_str) if as_of_str else datetime.utcnow().date()

    conn = sqlite3.connect("data/recommendations.db")
    store = CorroborationStore(conn)
    store.init_schema()

    # Resolve run_id
    resolved_run_id = run_id if run_id is not None else store.latest_run_id()
    if resolved_run_id is None:
        click.echo(click.style("No corroboration runs found. Run `corroborate` first.", fg="yellow"))
        return

    candidates = store.load_candidates(resolved_run_id)
    if not candidates:
        click.echo(click.style(f"No candidate snapshots for run #{resolved_run_id}. Re-run `corroborate`.", fg="yellow"))
        return

    # Load spine tickers (themes.yaml + sp500.txt + nasdaq100.txt)
    spine: set[str] = set()
    themes_path = Path("config/universe/themes.yaml")
    if themes_path.exists():
        data = yaml.safe_load(themes_path.read_text())
        for tickers in data.get("themes", {}).values():
            spine.update(tickers)
    config_dir = Path("config/tickers")
    for fname in ("sp500.txt", "nasdaq100.txt"):
        fpath = config_dir / fname
        if fpath.exists():
            for line in fpath.read_text().splitlines():
                s = line.strip()
                if s and not s.startswith("#"):
                    spine.add(s)

    click.echo(click.style("\n⚠️  RESEARCH ONLY — no buy/sell signals\n", bold=True))
    click.echo(f"Surfacing from run #{resolved_run_id} ({as_of.isoformat()}) — {len(candidates)} candidate(s)")

    if dry_run:
        # Print what would be admitted without writing
        from domain.corroboration_models import ConvergenceTier
        _ADMIT_TIERS = {ConvergenceTier.STRONG, ConvergenceTier.MODERATE}
        eligible = sorted(
            (c for c in candidates if c.convergence in _ADMIT_TIERS and c.verification == "ALL_VERIFIED"),
            key=lambda c: c.mean_convergence,
            reverse=True,
        )[:max_admissions]
        for c in eligible:
            if c.ticker in spine:
                click.echo(f"  ~ {c.ticker:<6} already in spine — would skip")
            else:
                click.echo(f"  ✓ {c.ticker:<6} convergence={c.convergence.value}")
        click.echo("\n[dry-run] no changes written.")
        return

    uc = SurfacingUseCase(
        store=store,
        spine_tickers=frozenset(spine),
        resolver=YFinanceResolver(),
        max_admissions=max_admissions,
    )
    active = uc.run(candidates=candidates, run_id=resolved_run_id, as_of=as_of)

    click.echo(f"\nActive discovered universe: {len(active)} ticker(s)")
    for entry in sorted(active, key=lambda e: e.ticker):
        click.echo(f"  {entry.ticker:<6} {entry.company_name:<30} ({entry.sector})  convergence={entry.convergence.value}")

    click.echo(click.style("\n⚠️  RESEARCH ONLY — no buy/sell signals\n", bold=True))
```

- [ ] **Step 2: Verify the command registers**

```bash
python -m application.cli surface-candidates --help
```

Expected:

```
Usage: python -m application.cli surface-candidates [OPTIONS]

  Surface corroborated tickers into the discovered-universe overlay.
  RESEARCH_ONLY.

Options:
  --run-id INTEGER  Corroboration run ID to read (default: latest)
  --date TEXT       As-of date YYYY-MM-DD for TTL (default: today UTC)
  --max INTEGER     Max tickers to admit this run  [default: 10]
  --dry-run         Print admissions without writing to store
  --help            Show this message and exit.
```

- [ ] **Step 3: Run mypy**

```bash
make typecheck
```

Expected: `Success: no issues found`

- [ ] **Step 4: Run smoke test**

```bash
make test-smoke
```

Expected: all smoke tests pass.

- [ ] **Step 5: Commit**

```bash
git add application/cli/scan_commands.py
git commit -m "feat(cli): add surface-candidates command for SP2 corroboration overlay"
```

---

## Task 9: Final gate

- [ ] **Step 1: Run full test suite**

```bash
make test-fast
```

Expected: all tests pass (including the ~23 existing SP7 tests).

- [ ] **Step 2: Run mypy strict**

```bash
make typecheck
```

Expected: `Success: no issues found`

- [ ] **Step 3: Update `docs/STATUS.md`**

Overwrite `docs/STATUS.md` with:

```markdown
# STATUS — multi-modal-stock-recommender

**As of:** 2026-06-22 (SP2 complete)
**Branch:** `feat/corroboration-engine` (off `develop`) SP1+SP2 done, PR #73 deferred
**Phase:** Corroboration engine SP2 BUILT — candidate surfacing + discovered-universe overlay live

## NEXT ACTION

SP3: Screener revamp — consume discovered universe from `HybridUniverseProvider`.
Brief at `docs/superpowers/specs/2026-06-20-sp3-*.md`.
Workflow: brainstorming → writing-plans → subagent-driven-development.

## What SP2 added

- `CandidateSnapshot` / `DiscoveredEntry` dataclasses (domain)
- `TickerResolverPort` protocol + `YFinanceResolver` adapter
- `CorroborationStore`: `candidates_snapshot` + `discovered_tickers` tables + 5 new methods
- `SurfacingUseCase`: admission logic (STRONG/MODERATE + ALL_VERIFIED, cap 10/wk, TTL 2 dry weeks)
- `HybridUniverseProvider`: corroboration overlay as 3rd source (spine > corroboration > buzz)
- CLI: `surface-candidates` command with `--dry-run` support
- `corroborate` CLI now saves `CandidateSnapshot` after each run

## Gotchas

- Run `corroborate` before `surface-candidates` — snapshots must exist for the run-id
- `store=None` in `HybridUniverseProvider` disables overlay (backwards-compat, existing callers unbroken)
- Use `.venv` (uv-managed); worktree at `../corroboration-sp7`
```

- [ ] **Step 4: Commit STATUS update**

```bash
git add docs/STATUS.md
git commit -m "docs: STATUS — SP2 candidate surfacing complete"
```

---

## Self-Review Notes

Spec coverage verified:
- ✓ `DiscoveredEntry` + `CandidateSnapshot` → Task 1
- ✓ `TickerResolverPort` → Task 2
- ✓ Store schema + 3 new methods (`upsert_discovered`, `active_discovered`, `expire_discovered`) → Task 3
- ✓ `YFinanceResolver` adapter → Task 5
- ✓ `SurfacingUseCase` with all 8 admission pipeline steps → Task 6
- ✓ `HybridUniverseProvider` `_corroboration_overlay()` + optional `store` param → Task 7
- ✓ `surface-candidates` CLI with `--dry-run` + RESEARCH_ONLY banner → Task 8
- ✓ All 11 spec tests present in Task 6 tests
- ✓ `save_candidates` / `load_candidates` / `latest_run_id` gap from spec filled → Task 3 + 4
- ✓ Backwards compat: `store=None` → overlay disabled, no existing test breaks
