# Design — SP2: Candidate Surfacing

**Date:** 2026-06-22
**Branch:** `feat/corroboration-engine` (off SP1)
**Status:** Approved, ready for implementation plan
**Depends on:** SP1 Corroboration Engine (`CorroboratedCandidate`, `CorroborationStore`)

---

## Purpose

Let genuinely new tickers (not in `sp500.txt`/`nasdaq100.txt`/`themes.yaml`) enter the scoring
universe when the weekly corroboration engine flags them at STRONG or MODERATE convergence with
full citation verification. Today the universe is frozen at ~120 static tickers.

---

## Decisions

| Question | Decision | Rationale |
|---|---|---|
| Admission threshold | STRONG + MODERATE, ALL_VERIFIED only | Double-gate: corroboration tier + downstream cmin/dmin |
| TTL | 2 dry weeks; WEAK counts as dry | Stories that go quiet for 2 runs are stale |
| De-dup | Skip + log at DEBUG level | Free observability on spine overlap |
| Approach | `SurfacingUseCase` (Approach 2) | Respects hexagonal: use case orchestrates, provider reads result |

---

## Architecture

```
CorroborationUseCase (SP1)
    └─ produces CorroboratedCandidate list + run_id

SurfacingUseCase (SP2, new)
    ├─ reads  CorroborationStore.load_candidates(run_id)
    ├─ admits STRONG/MODERATE + ALL_VERIFIED, cap 10/wk
    ├─ resolves ticker → company_name, sector via TickerResolverPort
    ├─ writes  CorroborationStore.upsert_discovered(...)
    └─ expires CorroborationStore.expire_discovered(as_of, dry_weeks=2)

HybridUniverseProvider (modified)
    ├─ _spine()                  → themes.yaml tickers
    ├─ _corroboration_overlay()  → CorroborationStore.active_discovered()  ← NEW
    └─ _buzz_discovery()         → BuzzDiscoveryPort.scan_sources()
```

---

## Section 1: Data model

### New table: `discovered_tickers` (added to `CorroborationStore.init_schema()`)

```sql
CREATE TABLE IF NOT EXISTS discovered_tickers (
    ticker       TEXT PRIMARY KEY,
    company_name TEXT,
    sector       TEXT,
    first_seen   TEXT NOT NULL,
    last_seen    TEXT NOT NULL,
    convergence  TEXT NOT NULL,
    run_id       INTEGER
);
```

### New dataclass: `DiscoveredEntry` (in `domain/corroboration_models.py`)

```python
@dataclass(frozen=True)
class DiscoveredEntry:
    ticker: str
    company_name: str
    sector: str
    first_seen: date
    last_seen: date
    convergence: ConvergenceTier
```

### New `CorroborationStore` methods

| Method | Signature | Behaviour |
|---|---|---|
| `upsert_discovered` | `(ticker, company_name, sector, as_of, convergence, run_id) → None` | INSERT or UPDATE last_seen/convergence |
| `active_discovered` | `(as_of: date, dry_weeks: int = 2) → list[DiscoveredEntry]` | rows where last_seen >= as_of - dry_weeks*7 |
| `expire_discovered` | `(as_of: date, dry_weeks: int = 2) → int` | DELETE stale rows, return count removed |

---

## Section 2: `SurfacingUseCase`

**File:** `application/surfacing_use_case.py`

```python
class SurfacingUseCase:
    def __init__(
        self,
        store: CorroborationStore,
        spine_tickers: frozenset[str],
        resolver: TickerResolverPort,
        max_admissions: int = 10,
    ): ...

    def run(
        self,
        candidates: list[CorroboratedCandidate],
        run_id: int,
        as_of: date,
    ) -> list[DiscoveredEntry]: ...
```

**Admission pipeline (in order):**

1. Filter `convergence in {STRONG, MODERATE}` AND `verification == "ALL_VERIFIED"`
2. Sort descending by `mean_convergence`
3. Skip if ticker in `spine_tickers` → `logger.debug("[surfacing] {} already in spine, skipping")`
4. Admit up to `max_admissions` tickers
5. Resolve each via `TickerResolverPort.resolve(ticker) → (company_name, sector)`;
   on failure use `("", "unknown")` — resolution failure does NOT block admission
6. `store.upsert_discovered(...)` for each admitted ticker
7. `store.expire_discovered(as_of)` — prune stale rows
8. Return `store.active_discovered(as_of)`

---

## Section 3: `TickerResolverPort`

**New protocol in `domain/ports.py`:**

```python
class TickerResolverPort(Protocol):
    def resolve(self, ticker: str) -> tuple[str, str]: ...  # (company_name, sector)
```

**Adapter:** `adapters/data/yfinance_resolver.py`
- Calls `yf.Ticker(ticker).info`, extracts `longName` and `sector`
- Wraps in try/except; returns `("", "unknown")` on any error

---

## Section 4: `HybridUniverseProvider` changes

`__init__` gains one optional param:

```python
store: CorroborationStore | None = None  # None = overlay disabled (backwards compat)
```

New private method:

```python
def _corroboration_overlay(self, now: datetime) -> dict[str, str]:
    if self._store is None:
        return {}
    return {e.ticker: "corroboration" for e in self._store.active_discovered(now.date())}
```

`get_universe()` merge order (priority: spine > corroboration > buzz):

1. Spine tickers
2. Corroboration overlay — skip+log if already in spine
3. Buzz discovery — skip if already seen

---

## Section 5: CLI

**Command:** `surface-candidates` added to `application/cli/scan_commands.py`

```
python -m application.cli surface-candidates
  [--run-id INT]      corroboration run to read (default: latest)
  [--date YYYY-MM-DD] as-of date for TTL (default: today UTC)
  [--max INT]         admission cap (default: 10)
  [--dry-run]         print admissions without writing to store
```

Output includes mandatory `⚠️  RESEARCH ONLY` banner. Prints admitted tickers,
skipped spine overlaps, and expired count.

---

## Section 6: Tests

**File:** `tests/test_surfacing_use_case.py`

| Test | Coverage |
|---|---|
| `test_admits_strong_all_verified` | STRONG+ALL_VERIFIED → admitted |
| `test_admits_moderate_all_verified` | MODERATE+ALL_VERIFIED → admitted |
| `test_rejects_weak` | WEAK skipped regardless of verification |
| `test_rejects_partial_verification` | STRONG+PARTIAL → skipped |
| `test_dedup_spine` | spine ticker → skipped + debug log |
| `test_cap_at_max_admissions` | 15 eligible, cap=10 → 10 admitted (sorted by mean_convergence) |
| `test_ttl_expire` | last_seen 15 days ago → expired on next run |
| `test_ttl_refresh` | same ticker reappears → last_seen updated, not expired |
| `test_resolver_failure_still_admits` | yfinance throws → admitted with company_name="" sector="unknown" |
| `test_hybrid_universe_corroboration_overlay` | `get_universe()` includes discovered tickers |
| `test_hybrid_universe_dedup_log` | discovered ticker in spine → debug log, not duplicated |

All tests use in-memory SQLite + `FakeTickerResolver`. No real yfinance calls in CI.

---

## Files touched

| File | Change |
|---|---|
| `domain/corroboration_models.py` | Add `DiscoveredEntry` dataclass |
| `domain/ports.py` | Add `TickerResolverPort` protocol |
| `adapters/data/corroboration_store.py` | New table + 3 new methods |
| `adapters/data/yfinance_resolver.py` | New adapter (thin yfinance wrapper) |
| `application/surfacing_use_case.py` | New use case |
| `adapters/data/hybrid_universe_provider.py` | Add `_corroboration_overlay()`, optional `store` param |
| `application/cli/scan_commands.py` | New `surface-candidates` command |
| `tests/test_surfacing_use_case.py` | 11 new tests |

---

## Out of scope (SP2)

- No buy language anywhere — RESEARCH_ONLY throughout
- No change to existing screen/scan universes (SP3)
- No watchlist concept — MODERATE goes to scan universe directly (same as STRONG)
- No forward-validation wiring (SP5)
