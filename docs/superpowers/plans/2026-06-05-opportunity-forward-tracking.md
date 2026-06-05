# Evidence-First Opportunity Surfacing & Forward-Tracking — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build an all-cap, multi-dimensional engine that surfaces emerging opportunities (conviction × early-divergence) as dated paper calls and forward-tracks each at 1w/1m/3m vs SPY and NDX, accruing a live track record.

**Architecture:** Hexagonal, Approach 3 — new pure domain models (`SurfacedCall`/`CallOutcome`) + divergence service + hybrid universe provider + two use-cases + 3 CLI commands. Reuses the conviction engine (`compute_conviction`, 8 sub-scores), `BuzzDiscoveryPort`, `MarketDataPort`, and Phase 8 `compute_signal_performance` as-is.

**Tech Stack:** Python 3.12, dataclasses/enums (domain), SQLite (store), click (CLI), pytest + Hypothesis, mypy strict, ruff/black/isort.

**Spec:** `docs/superpowers/specs/2026-06-05-opportunity-forward-tracking-design.md`. **Branch:** `feat/opportunity-forward-tracking`.

**Cross-cutting rules (every task):** TDD (failing test → run-fail → minimal impl → run-pass → commit). No network in tests — fakes only. `domain/` imports only stdlib/typing/dataclasses/datetime/enum. Point-in-time: every signal filtered ≤ `surfaced_at`. `make check` green before each commit; never `--no-verify`. Conventional commits.

---

## File structure

**New:**
- `domain/surfaced_call.py` — `OpportunityDirection`, `Horizon` enums; `EvidenceItem`, `SurfacedCall`, `CallOutcome`; `make_call_id`.
- `domain/divergence_service.py` — pure `divergence_score(...)`.
- `domain/universe.py` — `UniverseEntry`.
- `adapters/data/hybrid_universe_provider.py` — `HybridUniverseProvider`.
- `application/opportunity_scan_use_case.py` — `OpportunityScanUseCase`.
- `application/forward_tracking_use_case.py` — `ForwardTrackingUseCase`.
- `config/universe/themes.yaml` — curated thematic spine.
- `tests/fakes/fake_universe_provider.py`, `tests/fakes/fake_surfaced_call_store.py`.
- Tests: `tests/test_surfaced_call.py`, `test_divergence_service.py`, `test_hybrid_universe.py`, `test_opportunity_scan.py`, `test_forward_tracking.py`.
- `docs/adr/040-opportunity-forward-tracking.md`.

**Modified:**
- `domain/ports.py` — `UniverseProviderPort`, `SurfacedCallStorePort`.
- `adapters/data/sqlite_store.py` — `surfaced_calls` + `call_outcomes` tables + CRUD.
- `application/cli.py` — `scan-opportunities`, `resolve-calls`, `opportunity-report`.
- `CLAUDE.md`, `CONTEXT.md` — status.

---

## Task 0: ADR-040

**Files:** Create `docs/adr/040-opportunity-forward-tracking.md`

- [ ] **Step 1: Write the ADR.** Context (OOS finding: late institutional signals regime-fragile; thematic dims can't be backtested → forward-track). Decision (the 5 locked decisions from the spec). Alternatives (portfolio-first — rejected; pure index sweep — rejected). Consequences (paper-call semantics separate from real trades; evidence accrues over weeks).
- [ ] **Step 2: Commit.**

```bash
git add docs/adr/040-opportunity-forward-tracking.md
git commit -m "docs: ADR-040 evidence-first opportunity forward-tracking"
```

---

## Task 1: Domain models — `SurfacedCall`, `CallOutcome`

**Files:**
- Create: `domain/surfaced_call.py`
- Test: `tests/test_surfaced_call.py`

- [ ] **Step 1: Write the failing test.**

```python
# tests/test_surfaced_call.py
from datetime import datetime, timezone

import pytest

from domain.surfaced_call import (
    CallOutcome, EvidenceItem, Horizon, OpportunityDirection, SurfacedCall, make_call_id,
)

def _utc(y, m, d):
    return datetime(y, m, d, tzinfo=timezone.utc)

def test_make_call_id_is_deterministic():
    t = _utc(2026, 6, 5)
    assert make_call_id("ASTS", t) == "ASTS_20260605"

def test_surfaced_call_valid():
    call = SurfacedCall(
        call_id="ASTS_20260605", ticker="ASTS", surfaced_at=_utc(2026, 6, 5),
        conviction=7.5, divergence_score=8.0, direction=OpportunityDirection.BUY,
        evidence=(EvidenceItem("event_signal", 9.0, "SpaceX IPO halo"),),
        theme="space", cap_tier="small", spy_at_surface=540.0, ndx_at_surface=470.0,
    )
    assert call.ticker == "ASTS"
    assert call.direction is OpportunityDirection.BUY

@pytest.mark.parametrize("conv", [-1.0, 11.0])
def test_surfaced_call_rejects_out_of_range_conviction(conv):
    with pytest.raises(ValueError):
        SurfacedCall(
            call_id="X_20260605", ticker="X", surfaced_at=_utc(2026, 6, 5),
            conviction=conv, divergence_score=5.0, direction=OpportunityDirection.BUY,
            evidence=(), theme=None, cap_tier="mid", spy_at_surface=1.0, ndx_at_surface=1.0,
        )

def test_surfaced_call_requires_tz_aware():
    with pytest.raises(ValueError):
        SurfacedCall(
            call_id="X_20260605", ticker="X", surfaced_at=datetime(2026, 6, 5),
            conviction=5.0, divergence_score=5.0, direction=OpportunityDirection.BUY,
            evidence=(), theme=None, cap_tier="mid", spy_at_surface=1.0, ndx_at_surface=1.0,
        )

def test_horizon_days():
    assert (Horizon.W1.value, Horizon.M1.value, Horizon.M3.value) == (7, 30, 90)

def test_call_outcome_beats():
    oc = CallOutcome(
        call_id="ASTS_20260605", horizon=Horizon.M1, resolved_at=_utc(2026, 7, 5),
        entry_price=10.0, exit_price=13.0, forward_return=0.30,
        spy_return=0.05, ndx_return=0.04, beat_spy=True, beat_ndx=True, beat_both=True,
    )
    assert oc.beat_both is True
```

- [ ] **Step 2: Run, expect fail.** `pytest tests/test_surfaced_call.py -q` → `ModuleNotFoundError: domain.surfaced_call`.

- [ ] **Step 3: Implement.**

```python
# domain/surfaced_call.py
"""Paper-call models for the opportunity forward-tracking engine. Pure domain."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import Enum


class OpportunityDirection(Enum):
    BUY = "buy"                # a surfaced emerging opportunity
    SELL_WATCH = "sell_watch"  # a held name surfacing with deteriorating signals


class Horizon(Enum):
    W1 = 7    # calendar days
    M1 = 30
    M3 = 90


def make_call_id(ticker: str, surfaced_at: datetime) -> str:
    return f"{ticker}_{surfaced_at:%Y%m%d}"


@dataclass(frozen=True)
class EvidenceItem:
    dimension: str
    score: float
    note: str


@dataclass(frozen=True)
class SurfacedCall:
    call_id: str
    ticker: str
    surfaced_at: datetime  # tz-aware; POINT-IN-TIME ANCHOR
    conviction: float
    divergence_score: float
    direction: OpportunityDirection
    evidence: tuple[EvidenceItem, ...]
    theme: str | None
    cap_tier: str
    spy_at_surface: float
    ndx_at_surface: float

    def __post_init__(self) -> None:
        if self.surfaced_at.tzinfo is None:
            raise ValueError("surfaced_at must be timezone-aware")
        for name, val in (("conviction", self.conviction), ("divergence_score", self.divergence_score)):
            if not 0.0 <= val <= 10.0:
                raise ValueError(f"{name} must be in [0, 10], got {val}")


@dataclass(frozen=True)
class CallOutcome:
    call_id: str
    horizon: Horizon
    resolved_at: datetime
    entry_price: float
    exit_price: float
    forward_return: float
    spy_return: float
    ndx_return: float
    beat_spy: bool
    beat_ndx: bool
    beat_both: bool
```

- [ ] **Step 4: Run, expect pass.** `pytest tests/test_surfaced_call.py -q` → all pass.
- [ ] **Step 5: Commit.**

```bash
git add domain/surfaced_call.py tests/test_surfaced_call.py
git commit -m "feat: SurfacedCall + CallOutcome paper-call domain models"
```

---

## Task 2: Divergence service (the "early" signal)

**Files:**
- Create: `domain/divergence_service.py`
- Test: `tests/test_divergence_service.py`

Design: divergence is high when **buzz frequency is accelerating** (more mentions recently than the trailing baseline) **while price has not yet moved**. Inputs are buzz event timestamps (robust to unknown `BuzzSignal` magnitude fields) + a price series + current sentiment. Neutral 5.0 with no buzz.

- [ ] **Step 1: Write the failing test.**

```python
# tests/test_divergence_service.py
from datetime import datetime, timedelta, timezone

from domain.divergence_service import divergence_score

NOW = datetime(2026, 6, 5, tzinfo=timezone.utc)

def _prices(flat=True):
    # 40 daily points; flat or already-ran
    out = []
    for i in range(40):
        day = NOW - timedelta(days=39 - i)
        price = 100.0 if flat else (100.0 + i * 2.0)  # ran up if not flat
        out.append((day, price))
    return out

def test_no_buzz_is_neutral():
    assert divergence_score([], _prices(), 0.5, NOW) == 5.0

def test_rising_buzz_flat_price_scores_high():
    # heavy buzz in last 7 days, none before; price flat → strong divergence
    buzz = [NOW - timedelta(days=d) for d in (1, 2, 2, 3, 4, 5, 6)]
    assert divergence_score(buzz, _prices(flat=True), 0.7, NOW) > 6.5

def test_rising_buzz_but_price_already_ran_scores_lower():
    buzz = [NOW - timedelta(days=d) for d in (1, 2, 2, 3, 4, 5, 6)]
    high = divergence_score(buzz, _prices(flat=True), 0.7, NOW)
    ran = divergence_score(buzz, _prices(flat=False), 0.7, NOW)
    assert ran < high

def test_score_clamped_to_range():
    buzz = [NOW - timedelta(days=1)] * 50
    s = divergence_score(buzz, _prices(flat=True), 1.0, NOW)
    assert 1.0 <= s <= 10.0
```

- [ ] **Step 2: Run, expect fail.** `ModuleNotFoundError: domain.divergence_service`.

- [ ] **Step 3: Implement.**

```python
# domain/divergence_service.py
"""Early-signal divergence: buzz accelerating while price has not moved. Pure."""
from __future__ import annotations

from datetime import datetime, timedelta

_RECENT_DAYS = 7
_BASE_DAYS = 30  # the 30 days before the recent window


def _count_between(times: list[datetime], lo: datetime, hi: datetime) -> int:
    return sum(1 for t in times if lo < t <= hi)


def _recent_return(price_series: list[tuple[datetime, float]], now: datetime) -> float:
    if len(price_series) < 2:
        return 0.0
    asc = sorted(price_series, key=lambda p: p[0])
    last = asc[-1][1]
    cutoff = now - timedelta(days=_RECENT_DAYS)
    prior = next((p for _, p in reversed(asc) if _ <= cutoff), asc[0][1])
    if prior == 0:
        return 0.0
    return (last - prior) / prior


def divergence_score(
    buzz_times: list[datetime],
    price_series: list[tuple[datetime, float]],
    sentiment: float,
    now: datetime,
) -> float:
    """0-10. High when buzz frequency is rising and price hasn't moved yet.
    Neutral 5.0 with no buzz. Inputs pre-filtered to <= now upstream."""
    if not buzz_times:
        return 5.0
    recent = _count_between(buzz_times, now - timedelta(days=_RECENT_DAYS), now)
    base = _count_between(
        buzz_times, now - timedelta(days=_RECENT_DAYS + _BASE_DAYS), now - timedelta(days=_RECENT_DAYS)
    )
    base_rate = (base / _BASE_DAYS) * _RECENT_DAYS  # expected recent count if flat
    buzz_accel = (recent - base_rate) / max(base_rate, 1.0)
    price_move = max(_recent_return(price_series, now), 0.0)
    raw = buzz_accel - price_move * 2.0
    score = 5.0 + raw * 5.0 + (sentiment - 0.5) * 2.0
    return max(1.0, min(10.0, score))
```

- [ ] **Step 4: Run, expect pass.**
- [ ] **Step 5: Commit.**

```bash
git add domain/divergence_service.py tests/test_divergence_service.py
git commit -m "feat: divergence_score — buzz-leads-price early signal"
```

---

## Task 3: `UniverseEntry` + ports

**Files:**
- Create: `domain/universe.py`
- Modify: `domain/ports.py` (append the two protocols)
- Test: `tests/test_surfaced_call.py` (append a port-conformance test) — or new `tests/test_universe.py`

- [ ] **Step 1: Write the failing test.**

```python
# tests/test_universe.py
from datetime import datetime, timezone

from domain.ports import SurfacedCallStorePort, UniverseProviderPort
from domain.universe import UniverseEntry

def test_universe_entry():
    e = UniverseEntry(ticker="ASTS", theme="space")
    assert e.ticker == "ASTS" and e.theme == "space"

def test_ports_are_runtime_checkable():
    class P:
        def get_universe(self, now): return []
    assert isinstance(P(), UniverseProviderPort)
```

- [ ] **Step 2: Run, expect fail.** `ImportError: cannot import name 'UniverseEntry'`.

- [ ] **Step 3: Implement.**

```python
# domain/universe.py
"""Universe membership entry. Pure domain."""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class UniverseEntry:
    ticker: str
    theme: str | None  # spine theme name, or "discovery"
```

Append to `domain/ports.py` (it already uses `@runtime_checkable` / `Protocol`; mirror that style and add imports `from domain.surfaced_call import CallOutcome, Horizon, SurfacedCall` and `from domain.universe import UniverseEntry` at top):

```python
@runtime_checkable
class UniverseProviderPort(Protocol):
    """Provides the scan universe (curated spine + dynamic discovery)."""

    def get_universe(self, now: datetime) -> list[UniverseEntry]: ...


@runtime_checkable
class SurfacedCallStorePort(Protocol):
    """Persistence for surfaced paper calls and their resolved outcomes."""

    def save_call(self, call: SurfacedCall) -> None: ...

    def get_call(self, call_id: str) -> SurfacedCall | None: ...

    def get_all_calls(self) -> list[SurfacedCall]: ...

    def get_due_calls(self, now: datetime) -> list[tuple[SurfacedCall, Horizon]]: ...

    def save_outcome(self, outcome: CallOutcome) -> None: ...

    def get_outcomes(self) -> list[CallOutcome]: ...
```

- [ ] **Step 4: Run, expect pass.**
- [ ] **Step 5: Commit.**

```bash
git add domain/universe.py domain/ports.py tests/test_universe.py
git commit -m "feat: UniverseEntry + UniverseProviderPort + SurfacedCallStorePort"
```

---

## Task 4: Thematic spine config

**Files:**
- Create: `config/universe/themes.yaml`
- Test: `tests/test_hybrid_universe.py` (the loader is exercised in Task 5; here just assert the YAML parses with expected themes)

- [ ] **Step 1: Write the failing test.**

```python
# tests/test_hybrid_universe.py  (created here, extended in Task 5)
from pathlib import Path

import yaml

def test_themes_yaml_has_space_and_memory():
    data = yaml.safe_load(Path("config/universe/themes.yaml").read_text())
    themes = data["themes"]
    assert "ASTS" in themes["space"]
    assert "MU" in themes["memory_storage"]
```

- [ ] **Step 2: Run, expect fail.** `FileNotFoundError`.

- [ ] **Step 3: Implement.**

```yaml
# config/universe/themes.yaml
# Curated thematic spine. Tickers always watched; discovery overlay adds the rest.
# Membership is a tunable starting set — extend as themes evolve.
themes:
  space:
    [ASTS, RKLB, LUNR, IRDM, HXL, RDW]
  memory_storage:
    [MU, WDC, SNDK, STX]
  ai_infra:
    [SMCI, VRT, ANET, COHR, CRDO]
  nuclear_energy:
    [SMR, OKLO, CCJ, LEU]
  defense:
    [LMT, RTX, NOC, KTOS, AVAV]
  biotech:
    [VKTX, CYTK, KRYS, EXEL, HALO]
```

- [ ] **Step 4: Run, expect pass.**
- [ ] **Step 5: Commit.**

```bash
git add config/universe/themes.yaml tests/test_hybrid_universe.py
git commit -m "feat: curated thematic universe spine (themes.yaml)"
```

---

## Task 5: Hybrid universe provider

**Files:**
- Create: `adapters/data/hybrid_universe_provider.py`, `tests/fakes/fake_universe_provider.py`
- Test: extend `tests/test_hybrid_universe.py`

Reuses `BuzzDiscoveryPort.scan_sources(now) -> list[BuzzSignal]` (each `BuzzSignal` has `.ticker`). Spine wins the theme; discovery names get theme `"discovery"`; discovery capped; on any discovery exception → spine-only.

- [ ] **Step 1: Write the failing tests + the fake.**

```python
# tests/fakes/fake_universe_provider.py
from __future__ import annotations

from datetime import datetime

from domain.universe import UniverseEntry


class FakeUniverseProvider:
    def __init__(self, entries: list[UniverseEntry] | None = None) -> None:
        self._entries = entries or []
        self.calls: list[datetime] = []

    def get_universe(self, now: datetime) -> list[UniverseEntry]:
        self.calls.append(now)
        return self._entries
```

```python
# append to tests/test_hybrid_universe.py
from datetime import datetime, timezone

from adapters.data.hybrid_universe_provider import HybridUniverseProvider
from tests.fakes.fake_buzz_discovery import FakeBuzzDiscovery
from domain.models import BuzzSignal

NOW = datetime(2026, 6, 5, tzinfo=timezone.utc)

def _buzz(ticker):
    return BuzzSignal(ticker=ticker, source="reddit", sentiment_raw=0.5, fetched_at=NOW)

def test_hybrid_merges_spine_and_discovery():
    prov = HybridUniverseProvider(
        themes_path="config/universe/themes.yaml",
        buzz_discovery=FakeBuzzDiscovery([_buzz("PLTR"), _buzz("ASTS")]),
    )
    uni = prov.get_universe(NOW)
    tickers = {e.ticker for e in uni}
    assert "ASTS" in tickers           # spine
    assert "PLTR" in tickers           # discovered, not in spine
    # ASTS came from spine, keeps its theme (not "discovery")
    asts = next(e for e in uni if e.ticker == "ASTS")
    assert asts.theme == "space"
    pltr = next(e for e in uni if e.ticker == "PLTR")
    assert pltr.theme == "discovery"

def test_discovery_failure_falls_back_to_spine():
    class Boom:
        def scan_sources(self, now): raise RuntimeError("network down")
        def get_buzz_signals(self, **k): return []
    prov = HybridUniverseProvider("config/universe/themes.yaml", Boom())
    uni = prov.get_universe(NOW)
    assert any(e.ticker == "ASTS" for e in uni)   # spine still present
```

- [ ] **Step 2: Run, expect fail.** `ModuleNotFoundError: adapters.data.hybrid_universe_provider`.

- [ ] **Step 3: Implement.**

```python
# adapters/data/hybrid_universe_provider.py
"""Hybrid universe: curated thematic spine + dynamic buzz-discovery overlay."""
from __future__ import annotations

from datetime import datetime
from pathlib import Path

import yaml
from loguru import logger

from domain.ports import BuzzDiscoveryPort
from domain.universe import UniverseEntry


class HybridUniverseProvider:
    def __init__(
        self,
        themes_path: str,
        buzz_discovery: BuzzDiscoveryPort,
        max_discovery: int = 50,
    ) -> None:
        self._themes_path = themes_path
        self._buzz = buzz_discovery
        self._max_discovery = max_discovery

    def _spine(self) -> dict[str, str]:
        data = yaml.safe_load(Path(self._themes_path).read_text())
        out: dict[str, str] = {}
        for theme, tickers in data.get("themes", {}).items():
            for t in tickers:
                out.setdefault(t, theme)  # first theme wins on overlap
        return out

    def get_universe(self, now: datetime) -> list[UniverseEntry]:
        spine = self._spine()
        entries = [UniverseEntry(ticker=t, theme=theme) for t, theme in spine.items()]
        try:
            signals = self._buzz.scan_sources(now)
        except Exception as exc:  # noqa: BLE001 - degrade gracefully
            logger.warning("buzz discovery failed, spine-only universe: {}", exc)
            return entries
        seen = set(spine)
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

- [ ] **Step 4: Run, expect pass.**
- [ ] **Step 5: Commit.**

```bash
git add adapters/data/hybrid_universe_provider.py tests/fakes/fake_universe_provider.py tests/test_hybrid_universe.py
git commit -m "feat: HybridUniverseProvider — thematic spine + discovery overlay"
```

---

## Task 6: SQLite store — `surfaced_calls` + `call_outcomes`

**Files:**
- Modify: `adapters/data/sqlite_store.py` (add two tables to `_SCHEMA`; add CRUD methods implementing `SurfacedCallStorePort`)
- Test: `tests/test_surfaced_call_store.py`

Mirror the existing pattern: tables in the module-level `_SCHEMA` string; `INSERT OR REPLACE`; `.fetchall()` + a `_row_to_*` helper. Evidence serialized as JSON.

- [ ] **Step 1: Write the failing test.** (Uses a real in-memory store — `SQLiteStore(":memory:")`.)

```python
# tests/test_surfaced_call_store.py
from datetime import datetime, timedelta, timezone

from adapters.data.sqlite_store import SQLiteStore
from domain.surfaced_call import (
    CallOutcome, EvidenceItem, Horizon, OpportunityDirection, SurfacedCall,
)

def _utc(y, m, d):
    return datetime(y, m, d, tzinfo=timezone.utc)

def _call(ticker="ASTS", at=None):
    at = at or _utc(2026, 5, 1)
    return SurfacedCall(
        call_id=f"{ticker}_{at:%Y%m%d}", ticker=ticker, surfaced_at=at,
        conviction=7.0, divergence_score=8.0, direction=OpportunityDirection.BUY,
        evidence=(EvidenceItem("event_signal", 9.0, "halo"),),
        theme="space", cap_tier="small", spy_at_surface=500.0, ndx_at_surface=440.0,
    )

def test_save_and_get_call_roundtrip():
    s = SQLiteStore(":memory:")
    c = _call()
    s.save_call(c)
    got = s.get_call(c.call_id)
    assert got == c            # frozen dataclass equality incl. evidence tuple

def test_due_calls_only_after_horizon_matures():
    s = SQLiteStore(":memory:")
    c = _call(at=_utc(2026, 5, 1))
    s.save_call(c)
    # 8 days later: only W1 (7d) is due
    due = s.get_due_calls(_utc(2026, 5, 9))
    assert (c, Horizon.W1) in due
    assert (c, Horizon.M1) not in due

def test_resolved_horizon_not_returned_again():
    s = SQLiteStore(":memory:")
    c = _call(at=_utc(2026, 5, 1))
    s.save_call(c)
    s.save_outcome(CallOutcome(
        call_id=c.call_id, horizon=Horizon.W1, resolved_at=_utc(2026, 5, 9),
        entry_price=10.0, exit_price=11.0, forward_return=0.1,
        spy_return=0.01, ndx_return=0.01, beat_spy=True, beat_ndx=True, beat_both=True,
    ))
    due = s.get_due_calls(_utc(2026, 5, 9))
    assert (c, Horizon.W1) not in due
    assert len(s.get_outcomes()) == 1
```

- [ ] **Step 2: Run, expect fail.** `AttributeError: 'SQLiteStore' object has no attribute 'save_call'`.

- [ ] **Step 3: Implement.** Add to the `_SCHEMA` string:

```sql
CREATE TABLE IF NOT EXISTS surfaced_calls (
    call_id TEXT PRIMARY KEY,
    ticker TEXT NOT NULL,
    surfaced_at TEXT NOT NULL,
    conviction REAL NOT NULL,
    divergence_score REAL NOT NULL,
    direction TEXT NOT NULL,
    evidence TEXT NOT NULL,
    theme TEXT,
    cap_tier TEXT NOT NULL,
    spy_at_surface REAL NOT NULL,
    ndx_at_surface REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS call_outcomes (
    call_id TEXT NOT NULL,
    horizon INTEGER NOT NULL,
    resolved_at TEXT NOT NULL,
    entry_price REAL NOT NULL,
    exit_price REAL NOT NULL,
    forward_return REAL NOT NULL,
    spy_return REAL NOT NULL,
    ndx_return REAL NOT NULL,
    beat_spy INTEGER NOT NULL,
    beat_ndx INTEGER NOT NULL,
    beat_both INTEGER NOT NULL,
    PRIMARY KEY (call_id, horizon)
);
```

Add methods to `SQLiteStore` (import `json`, `datetime`; reuse the existing `self._conn`):

```python
def save_call(self, call: SurfacedCall) -> None:
    self._conn.execute(
        """INSERT OR REPLACE INTO surfaced_calls
        (call_id, ticker, surfaced_at, conviction, divergence_score, direction,
         evidence, theme, cap_tier, spy_at_surface, ndx_at_surface)
        VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
        (
            call.call_id, call.ticker, call.surfaced_at.isoformat(),
            call.conviction, call.divergence_score, call.direction.value,
            json.dumps([[e.dimension, e.score, e.note] for e in call.evidence]),
            call.theme, call.cap_tier, call.spy_at_surface, call.ndx_at_surface,
        ),
    )
    self._conn.commit()

def _row_to_call(self, r: sqlite3.Row) -> SurfacedCall:
    return SurfacedCall(
        call_id=r["call_id"], ticker=r["ticker"],
        surfaced_at=datetime.fromisoformat(r["surfaced_at"]),
        conviction=r["conviction"], divergence_score=r["divergence_score"],
        direction=OpportunityDirection(r["direction"]),
        evidence=tuple(EvidenceItem(d, s, n) for d, s, n in json.loads(r["evidence"])),
        theme=r["theme"], cap_tier=r["cap_tier"],
        spy_at_surface=r["spy_at_surface"], ndx_at_surface=r["ndx_at_surface"],
    )

def get_call(self, call_id: str) -> SurfacedCall | None:
    row = self._conn.execute(
        "SELECT * FROM surfaced_calls WHERE call_id = ?", (call_id,)
    ).fetchone()
    return self._row_to_call(row) if row else None

def get_all_calls(self) -> list[SurfacedCall]:
    rows = self._conn.execute("SELECT * FROM surfaced_calls").fetchall()
    return [self._row_to_call(r) for r in rows]

def get_due_calls(self, now: datetime) -> list[tuple[SurfacedCall, Horizon]]:
    resolved = {
        (r["call_id"], r["horizon"])
        for r in self._conn.execute("SELECT call_id, horizon FROM call_outcomes").fetchall()
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
    self._conn.execute(
        """INSERT OR REPLACE INTO call_outcomes
        (call_id, horizon, resolved_at, entry_price, exit_price, forward_return,
         spy_return, ndx_return, beat_spy, beat_ndx, beat_both)
        VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
        (
            outcome.call_id, outcome.horizon.value, outcome.resolved_at.isoformat(),
            outcome.entry_price, outcome.exit_price, outcome.forward_return,
            outcome.spy_return, outcome.ndx_return,
            int(outcome.beat_spy), int(outcome.beat_ndx), int(outcome.beat_both),
        ),
    )
    self._conn.commit()

def get_outcomes(self) -> list[CallOutcome]:
    rows = self._conn.execute("SELECT * FROM call_outcomes").fetchall()
    return [
        CallOutcome(
            call_id=r["call_id"], horizon=Horizon(r["horizon"]),
            resolved_at=datetime.fromisoformat(r["resolved_at"]),
            entry_price=r["entry_price"], exit_price=r["exit_price"],
            forward_return=r["forward_return"], spy_return=r["spy_return"],
            ndx_return=r["ndx_return"], beat_spy=bool(r["beat_spy"]),
            beat_ndx=bool(r["beat_ndx"]), beat_both=bool(r["beat_both"]),
        )
        for r in rows
    ]
```

Add imports at top of `sqlite_store.py`: `from datetime import datetime, timedelta` (if not present) and `from domain.surfaced_call import CallOutcome, EvidenceItem, Horizon, OpportunityDirection, SurfacedCall`.

- [ ] **Step 4: Run, expect pass.** `pytest tests/test_surfaced_call_store.py -q`.
- [ ] **Step 5: Commit.**

```bash
git add adapters/data/sqlite_store.py tests/test_surfaced_call_store.py
git commit -m "feat: SQLite persistence for surfaced calls + call outcomes"
```

---

## Task 7: `OpportunityScanUseCase`

**Files:**
- Create: `application/opportunity_scan_use_case.py`, `tests/fakes/fake_surfaced_call_store.py`
- Test: `tests/test_opportunity_scan.py`

Injected deps (all duck-typed for fakes): `universe_provider`, `conviction_provider: Callable[[str, datetime], tuple[float, dict[str, float]]]` (returns conviction + the 8 sub-scores — wired to the real conviction engine in the CLI), `buzz_discovery`, `market_data`, `store`. Layered trigger: `conviction >= cmin AND divergence >= dmin`. Abstain → `[]`. Point-in-time: signals fetched with `end_date=now`.

- [ ] **Step 1: Write the failing test.**

```python
# tests/test_opportunity_scan.py
from datetime import datetime, timedelta, timezone

from application.opportunity_scan_use_case import OpportunityScanUseCase
from domain.surfaced_call import OpportunityDirection
from domain.universe import UniverseEntry
from domain.models import BuzzSignal, Signal
from tests.fakes.fake_universe_provider import FakeUniverseProvider
from tests.fakes.fake_buzz_discovery import FakeBuzzDiscovery
from tests.fakes.fake_market_data import FakeMarketData
from tests.fakes.fake_surfaced_call_store import FakeSurfacedCallStore

NOW = datetime(2026, 6, 5, tzinfo=timezone.utc)

def _prices(symbol):
    return [
        Signal(symbol=symbol, timestamp=NOW - timedelta(days=39 - i), price=100.0,
               volume=1.0, open_=100.0, high=100.0, low=100.0)
        for i in range(40)
    ]

def _md():
    return FakeMarketData(
        signals={"ASTS": _prices("ASTS"), "DUD": _prices("DUD"),
                 "SPY": _prices("SPY"), "QQQ": _prices("QQQ")},
        ticker_info={"ASTS": {"marketCap": 3e9}, "DUD": {"marketCap": 5e8}},
    )

def _conviction(high_ticker):
    def fn(ticker, now):
        if ticker == high_ticker:
            return 8.0, {"event_signal": 9.0, "smart_money": 7.0}
        return 3.0, {"event_signal": 3.0}
    return fn

def test_surfaces_qualifying_name_and_abstains_on_rest():
    buzz = FakeBuzzDiscovery([
        BuzzSignal(ticker="ASTS", source="reddit", sentiment_raw=0.7, fetched_at=NOW - timedelta(days=d))
        for d in (1, 2, 3, 4, 5)
    ])
    store = FakeSurfacedCallStore()
    uc = OpportunityScanUseCase(
        universe_provider=FakeUniverseProvider([
            UniverseEntry("ASTS", "space"), UniverseEntry("DUD", "space")]),
        conviction_provider=_conviction("ASTS"),
        buzz_discovery=buzz, market_data=_md(), store=store, cmin=6.0, dmin=6.0,
    )
    calls = uc.execute(NOW)
    tickers = [c.ticker for c in calls]
    assert tickers == ["ASTS"]                       # DUD failed conviction bar
    assert calls[0].direction is OpportunityDirection.BUY
    assert any(e.dimension == "divergence" for e in calls[0].evidence)
    assert store.saved and store.saved[0].ticker == "ASTS"

def test_abstention_returns_empty():
    store = FakeSurfacedCallStore()
    uc = OpportunityScanUseCase(
        universe_provider=FakeUniverseProvider([UniverseEntry("DUD", "space")]),
        conviction_provider=_conviction("NONE"),
        buzz_discovery=FakeBuzzDiscovery([]), market_data=_md(), store=store,
        cmin=6.0, dmin=6.0,
    )
    assert uc.execute(NOW) == []
    assert store.saved == []
```

Fake store:

```python
# tests/fakes/fake_surfaced_call_store.py
from __future__ import annotations

from datetime import datetime

from domain.surfaced_call import CallOutcome, Horizon, SurfacedCall


class FakeSurfacedCallStore:
    def __init__(self) -> None:
        self.saved: list[SurfacedCall] = []
        self.outcomes: list[CallOutcome] = []

    def save_call(self, call: SurfacedCall) -> None:
        self.saved.append(call)

    def get_call(self, call_id: str) -> SurfacedCall | None:
        return next((c for c in self.saved if c.call_id == call_id), None)

    def get_all_calls(self) -> list[SurfacedCall]:
        return list(self.saved)

    def get_due_calls(self, now: datetime) -> list[tuple[SurfacedCall, Horizon]]:
        from datetime import timedelta
        resolved = {(o.call_id, o.horizon) for o in self.outcomes}
        return [
            (c, h) for c in self.saved for h in Horizon
            if (c.call_id, h) not in resolved and now >= c.surfaced_at + timedelta(days=h.value)
        ]

    def save_outcome(self, outcome: CallOutcome) -> None:
        self.outcomes.append(outcome)

    def get_outcomes(self) -> list[CallOutcome]:
        return list(self.outcomes)
```

- [ ] **Step 2: Run, expect fail.** `ModuleNotFoundError: application.opportunity_scan_use_case`.

- [ ] **Step 3: Implement.**

```python
# application/opportunity_scan_use_case.py
"""Surface emerging opportunities: conviction x early-divergence, with abstention."""
from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any, Callable

from domain.divergence_service import divergence_score
from domain.surfaced_call import (
    EvidenceItem, OpportunityDirection, SurfacedCall, make_call_id,
)

ConvictionProvider = Callable[[str, datetime], tuple[float, dict[str, float]]]


def _cap_tier(market_cap: float) -> str:
    if market_cap >= 1e10:
        return "large"
    if market_cap >= 2e9:
        return "mid"
    return "small"


class OpportunityScanUseCase:
    def __init__(
        self,
        universe_provider: Any,
        conviction_provider: ConvictionProvider,
        buzz_discovery: Any,
        market_data: Any,
        store: Any,
        cmin: float = 6.0,
        dmin: float = 6.0,
    ) -> None:
        self._universe = universe_provider
        self._conviction = conviction_provider
        self._buzz = buzz_discovery
        self._md = market_data
        self._store = store
        self._cmin = cmin
        self._dmin = dmin

    def _price_series(self, ticker: str, now: datetime) -> list[tuple[datetime, float]]:
        start = now - timedelta(days=40)
        sigs = self._md.get_signals(ticker, now, start_date=start, end_date=now)
        return [(s.timestamp, s.price) for s in sigs]

    def _benchmark(self, symbol: str, now: datetime) -> float:
        sigs = self._md.get_signals(symbol, now, end_date=now)
        return sigs[-1].price if sigs else 0.0

    def execute(self, now: datetime, *, allow_abstention: bool = True) -> list[SurfacedCall]:
        spy = self._benchmark("SPY", now)
        ndx = self._benchmark("QQQ", now)
        surfaced: list[SurfacedCall] = []
        for entry in self._universe.get_universe(now):
            conviction, sub_scores = self._conviction(entry.ticker, now)
            buzz = self._buzz.get_buzz_signals(ticker=entry.ticker, end_date=now)
            buzz_times = [b.fetched_at for b in buzz if b.fetched_at is not None]
            sentiment = (
                sum(getattr(b, "sentiment_raw", 0.0) for b in buzz) / len(buzz)
                if buzz else 0.5
            )
            # normalize sentiment_raw (-1..1) to 0..1
            sentiment = max(0.0, min(1.0, 0.5 + sentiment / 2.0))
            divergence = divergence_score(
                buzz_times, self._price_series(entry.ticker, now), sentiment, now
            )
            if conviction < self._cmin or divergence < self._dmin:
                continue
            info = self._md.get_ticker_info(entry.ticker)
            evidence = tuple(
                EvidenceItem(dim, score, f"{dim} contribution")
                for dim, score in sorted(sub_scores.items(), key=lambda kv: -kv[1])
            ) + (EvidenceItem("divergence", divergence, "buzz accelerating, price lagging"),)
            call = SurfacedCall(
                call_id=make_call_id(entry.ticker, now), ticker=entry.ticker,
                surfaced_at=now, conviction=conviction, divergence_score=divergence,
                direction=OpportunityDirection.BUY, evidence=evidence, theme=entry.theme,
                cap_tier=_cap_tier(float(info.get("marketCap", 0.0))),
                spy_at_surface=spy, ndx_at_surface=ndx,
            )
            self._store.save_call(call)
            surfaced.append(call)
        surfaced.sort(key=lambda c: (c.conviction + c.divergence_score), reverse=True)
        if not surfaced and allow_abstention:
            return []
        return surfaced
```

- [ ] **Step 4: Run, expect pass.** `pytest tests/test_opportunity_scan.py -q`.
- [ ] **Step 5: Commit.**

```bash
git add application/opportunity_scan_use_case.py tests/fakes/fake_surfaced_call_store.py tests/test_opportunity_scan.py
git commit -m "feat: OpportunityScanUseCase — layered trigger + abstention"
```

---

## Task 8: `ForwardTrackingUseCase`

**Files:**
- Create: `application/forward_tracking_use_case.py`
- Test: `tests/test_forward_tracking.py`

Resolves each due `(call, horizon)` using `MarketDataPort.get_signals` for entry/exit/benchmark prices; writes `CallOutcome`. `get_track_record()` maps outcomes→synthetic `TradeOutcome`s (signals = evidence dims scoring ≥6) and reuses Phase 8 `compute_signal_performance`.

- [ ] **Step 1: Write the failing test.**

```python
# tests/test_forward_tracking.py
from datetime import datetime, timedelta, timezone

from application.forward_tracking_use_case import ForwardTrackingUseCase
from domain.surfaced_call import EvidenceItem, OpportunityDirection, SurfacedCall, Horizon
from domain.models import Signal
from tests.fakes.fake_market_data import FakeMarketData
from tests.fakes.fake_surfaced_call_store import FakeSurfacedCallStore

def _utc(y, m, d):
    return datetime(y, m, d, tzinfo=timezone.utc)

def _price_points(symbol, start, days, fn):
    return [
        Signal(symbol=symbol, timestamp=start + timedelta(days=i), price=fn(i),
               volume=1.0, open_=fn(i), high=fn(i), low=fn(i))
        for i in range(days)
    ]

def _call():
    at = _utc(2026, 5, 1)
    return SurfacedCall(
        call_id="ASTS_20260501", ticker="ASTS", surfaced_at=at, conviction=7.0,
        divergence_score=8.0, direction=OpportunityDirection.BUY,
        evidence=(EvidenceItem("event_signal", 9.0, "halo"),),
        theme="space", cap_tier="small", spy_at_surface=500.0, ndx_at_surface=440.0,
    )

def test_resolves_w1_outcome_vs_benchmarks():
    start = _utc(2026, 5, 1)
    md = FakeMarketData(signals={
        "ASTS": _price_points("ASTS", start, 20, lambda i: 10.0 + i),   # +1/day
        "SPY": _price_points("SPY", start, 20, lambda i: 500.0),        # flat
        "QQQ": _price_points("QQQ", start, 20, lambda i: 440.0),        # flat
    })
    store = FakeSurfacedCallStore()
    store.save_call(_call())
    uc = ForwardTrackingUseCase(store=store, market_data=md)
    outcomes = uc.resolve_due_calls(_utc(2026, 5, 9))   # only W1 (7d) mature
    w1 = [o for o in outcomes if o.horizon is Horizon.W1]
    assert len(w1) == 1
    assert w1[0].forward_return > 0          # ASTS rose
    assert w1[0].beat_spy is True            # SPY flat
    assert len(store.get_outcomes()) == 1

def test_track_record_aggregates_by_signal():
    start = _utc(2026, 5, 1)
    md = FakeMarketData(signals={
        "ASTS": _price_points("ASTS", start, 40, lambda i: 10.0 + i),
        "SPY": _price_points("SPY", start, 40, lambda i: 500.0),
        "QQQ": _price_points("QQQ", start, 40, lambda i: 440.0),
    })
    store = FakeSurfacedCallStore()
    store.save_call(_call())
    uc = ForwardTrackingUseCase(store=store, market_data=md)
    uc.resolve_due_calls(_utc(2026, 8, 1))   # all horizons mature
    perfs = uc.get_track_record()
    names = {p.signal_name for p in perfs}
    assert "event_signal" in names           # evidence dim became a tracked signal
```

- [ ] **Step 2: Run, expect fail.** `ModuleNotFoundError: application.forward_tracking_use_case`.

- [ ] **Step 3: Implement.**

```python
# application/forward_tracking_use_case.py
"""Resolve surfaced calls at 1w/1m/3m vs SPY+NDX; feed Phase 8 signal performance."""
from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any

from domain.outcome import TradeOutcome
from domain.outcome_service import compute_signal_performance
from domain.surfaced_call import CallOutcome

_EVIDENCE_SIGNAL_MIN = 6.0  # an evidence dim counts as a "signal" when it scored >= this


def _price_on_or_after(md: Any, ticker: str, target: datetime, now: datetime) -> float | None:
    sigs = md.get_signals(ticker, now, start_date=target, end_date=now)
    asc = sorted(sigs, key=lambda s: s.timestamp)
    return asc[0].price if asc else None


def _price_on_or_before(md: Any, ticker: str, target: datetime) -> float | None:
    sigs = md.get_signals(ticker, target)
    asc = sorted(sigs, key=lambda s: s.timestamp)
    return asc[-1].price if asc else None


class ForwardTrackingUseCase:
    def __init__(self, store: Any, market_data: Any) -> None:
        self._store = store
        self._md = market_data

    def resolve_due_calls(self, now: datetime) -> list[CallOutcome]:
        resolved: list[CallOutcome] = []
        for call, horizon in self._store.get_due_calls(now):
            exit_target = call.surfaced_at + timedelta(days=horizon.value)
            entry = _price_on_or_before(self._md, call.ticker, call.surfaced_at)
            exit_p = _price_on_or_after(self._md, call.ticker, exit_target, now)
            spy_e = _price_on_or_before(self._md, "SPY", call.surfaced_at)
            spy_x = _price_on_or_after(self._md, "SPY", exit_target, now)
            ndx_e = _price_on_or_before(self._md, "QQQ", call.surfaced_at)
            ndx_x = _price_on_or_after(self._md, "QQQ", exit_target, now)
            if None in (entry, exit_p, spy_e, spy_x, ndx_e, ndx_x) or entry == 0:
                continue
            fwd = (exit_p - entry) / entry
            spy_r = (spy_x - spy_e) / spy_e if spy_e else 0.0
            ndx_r = (ndx_x - ndx_e) / ndx_e if ndx_e else 0.0
            outcome = CallOutcome(
                call_id=call.call_id, horizon=horizon, resolved_at=now,
                entry_price=entry, exit_price=exit_p, forward_return=fwd,
                spy_return=spy_r, ndx_return=ndx_r,
                beat_spy=fwd > spy_r, beat_ndx=fwd > ndx_r,
                beat_both=fwd > spy_r and fwd > ndx_r,
            )
            self._store.save_outcome(outcome)
            resolved.append(outcome)
        return resolved

    def get_track_record(self) -> list[Any]:
        by_id = {c.call_id: c for c in self._store.get_all_calls()}
        trade_outcomes: list[TradeOutcome] = []
        for oc in self._store.get_outcomes():
            call = by_id.get(oc.call_id)
            if call is None:
                continue
            signals = [e.dimension for e in call.evidence if e.score >= _EVIDENCE_SIGNAL_MIN]
            trade_outcomes.append(
                TradeOutcome(
                    ticker=call.ticker, buy_trade_id=f"{oc.call_id}:{oc.horizon.value}",
                    sell_trade_id=f"{oc.call_id}:{oc.horizon.value}:x",
                    buy_price=oc.entry_price, sell_price=oc.exit_price, quantity=1,
                    buy_date=call.surfaced_at.strftime("%Y-%m-%d"),
                    sell_date=oc.resolved_at.strftime("%Y-%m-%d"),
                    holding_days=oc.horizon.value, return_pct=oc.forward_return * 100.0,
                    return_dollar=oc.exit_price - oc.entry_price,
                    signals_at_entry=signals, conviction_at_entry=call.conviction,
                )
            )
        return compute_signal_performance(trade_outcomes)
```

> **Note for implementer:** confirm `TradeOutcome`'s field names against `domain/outcome.py` (the report used: ticker, buy_trade_id, sell_trade_id, buy_price, sell_price, quantity, buy_date, sell_date, holding_days, return_pct, return_dollar, signals_at_entry, conviction_at_entry). Adjust the constructor call if any differ.

- [ ] **Step 4: Run, expect pass.** `pytest tests/test_forward_tracking.py -q`.
- [ ] **Step 5: Commit.**

```bash
git add application/forward_tracking_use_case.py tests/test_forward_tracking.py
git commit -m "feat: ForwardTrackingUseCase — multi-horizon resolution + signal track record"
```

---

## Task 9: CLI commands

**Files:**
- Modify: `application/cli.py` (add 3 commands; add a `_build_opportunity_deps` helper that wires the real conviction engine into a `conviction_provider`)
- Test: `tests/test_opportunity_cli.py` (smoke — invoke via click `CliRunner` with monkeypatched deps, OR assert the command is registered and `--help` renders)

Because the real conviction path needs network adapters, the CLI smoke test asserts registration + help only (no network, rule #5). The real conviction wiring reuses `ConvictionScoringUseCase._compute_sub_scores` + `compute_conviction`.

- [ ] **Step 1: Write the failing test.**

```python
# tests/test_opportunity_cli.py
from click.testing import CliRunner

from application.cli import cli

def test_commands_registered():
    names = {c.name for c in cli.commands.values()}
    assert {"scan-opportunities", "resolve-calls", "opportunity-report"} <= names

def test_scan_help_renders():
    res = CliRunner().invoke(cli, ["scan-opportunities", "--help"])
    assert res.exit_code == 0
    assert "surface" in res.output.lower()
```

- [ ] **Step 2: Run, expect fail.** `AssertionError` (commands not registered).

- [ ] **Step 3: Implement.** Add to `application/cli.py` (mirror the existing `@cli.command` + `_build_dependencies` pattern). The conviction provider wraps the existing engine:

```python
@cli.command("scan-opportunities")
@click.option("--market", default="us")
@click.option("--date", default=None, help="Scan date (YYYY-MM-DD); default today")
@click.option("--cmin", default=6.0, show_default=True)
@click.option("--dmin", default=6.0, show_default=True)
def scan_opportunities(market: str, date: str | None, cmin: float, dmin: float) -> None:
    """Surface emerging all-cap opportunities (conviction x early-divergence) or abstain."""
    from datetime import timezone

    from adapters.data.hybrid_universe_provider import HybridUniverseProvider
    from application.opportunity_scan_use_case import OpportunityScanUseCase
    from domain.conviction import ConvictionWeights

    deps = _build_dependencies(market)
    now = (datetime.strptime(date, "%Y-%m-%d") if date else datetime.now()).replace(tzinfo=timezone.utc)
    md = deps["market_data"]
    weights = ConvictionWeights()

    buzz = deps["store"]  # SQLiteStore implements BuzzDiscoveryPort? If not, wire the real buzz adapter here.

    def conviction_provider(ticker: str, t: datetime) -> tuple[float, dict[str, float]]:
        from application.conviction_use_case import ConvictionScoringUseCase
        from domain.conviction_service import compute_conviction
        info = md.get_ticker_info(ticker)
        subs = ConvictionScoringUseCase._compute_sub_scores(
            features={}, ticker_signals=[], scan_time=t, buzz_signals=None,
            ticker_info=info, recommendation=None,
        )
        return compute_conviction(subs, weights), subs

    universe = HybridUniverseProvider("config/universe/themes.yaml", buzz_discovery=_real_buzz(deps))
    uc = OpportunityScanUseCase(
        universe_provider=universe, conviction_provider=conviction_provider,
        buzz_discovery=_real_buzz(deps), market_data=md, store=deps["store"],
        cmin=cmin, dmin=dmin,
    )
    calls = uc.execute(now)
    if not calls:
        click.echo("No high-conviction opportunities today — engine sitting out.")
        return
    for c in calls:
        click.echo(f"{c.ticker:6} conv={c.conviction:.1f} div={c.divergence_score:.1f} "
                   f"theme={c.theme} | {c.evidence[0].dimension}")


@cli.command("resolve-calls")
@click.option("--market", default="us")
@click.option("--date", default=None, help="Resolution date (YYYY-MM-DD); default today")
def resolve_calls(market: str, date: str | None) -> None:
    """Resolve matured calls at 1w/1m/3m vs SPY+NDX and update the track record."""
    from datetime import timezone

    from application.forward_tracking_use_case import ForwardTrackingUseCase

    deps = _build_dependencies(market)
    now = (datetime.strptime(date, "%Y-%m-%d") if date else datetime.now()).replace(tzinfo=timezone.utc)
    uc = ForwardTrackingUseCase(store=deps["store"], market_data=deps["market_data"])
    resolved = uc.resolve_due_calls(now)
    click.echo(f"Resolved {len(resolved)} (call, horizon) outcomes.")


@cli.command("opportunity-report")
@click.option("--market", default="us")
def opportunity_report(market: str) -> None:
    """Show the accruing per-signal track record vs SPY+NDX."""
    from application.forward_tracking_use_case import ForwardTrackingUseCase

    deps = _build_dependencies(market)
    uc = ForwardTrackingUseCase(store=deps["store"], market_data=deps["market_data"])
    for p in sorted(uc.get_track_record(), key=lambda x: -x.hit_rate):
        click.echo(f"{p.signal_name:20} hit={p.hit_rate:5.1f}% n={p.total_trades} "
                   f"avg={p.avg_return_pct:+.1f}%")
```

Add a `_real_buzz(deps)` helper that returns the project's real `BuzzDiscoveryPort` adapter (find the existing buzz-discovery adapter under `adapters/data/`; if the daily-scan already builds one, reuse that wiring). If no standalone adapter exists, wire the sentiment adapters the daily-scan uses.

> **Note for implementer:** `_build_dependencies` does not currently expose a buzz-discovery adapter. Inspect how `make daily-scan` / the daily scan pipeline builds buzz discovery and reuse it; expose it via `_build_dependencies` (add a `"buzz_discovery"` key) rather than the `store` placeholder shown above. Keep this wiring out of the smoke test (network).

- [ ] **Step 4: Run, expect pass.** `pytest tests/test_opportunity_cli.py -q`.
- [ ] **Step 5: Commit.**

```bash
git add application/cli.py tests/test_opportunity_cli.py
git commit -m "feat: scan-opportunities, resolve-calls, opportunity-report CLI"
```

---

## Task 10: Docs + full gate

**Files:** Modify `CLAUDE.md`, `CONTEXT.md`.

- [ ] **Step 1:** Add a "Done (Leg-2 sub-project 1 — Opportunity Forward-Tracking)" section to `CLAUDE.md` phase status (surfacing + multi-horizon forward-tracking + hybrid universe + abstention) and update `CONTEXT.md` terminology (SurfacedCall, CallOutcome, divergence_score, forward-tracking).
- [ ] **Step 2:** Run the full gate: `make check`. Expected: all pass, coverage ≥90%.
- [ ] **Step 3: Commit.**

```bash
git add CLAUDE.md CONTEXT.md
git commit -m "docs: record Leg-2 sub-project 1 (opportunity forward-tracking)"
```

---

## Self-review checklist (run before handoff)

- [ ] Every DoD criterion (spec 1–10) maps to a task: surfacing+evidence→T7; 8 dims live→T9 wiring; discovery overlay→T5; point-in-time→T7/T8; multi-horizon resolution vs SPY+NDX→T8; abstention→T7; track record→T8/T9; leakage timing→T6/T8; quality gate→T10; domain purity→T1/T2/T3.
- [ ] No placeholders left except the two explicit implementer notes (TradeOutcome field confirmation in T8; real buzz-discovery wiring in T9) — both point to exact files to check.
- [ ] Type consistency: `SurfacedCall`/`CallOutcome`/`Horizon`/`OpportunityDirection`/`EvidenceItem`/`UniverseEntry` used identically across T1, T3, T6, T7, T8; `conviction_provider` returns `(float, dict[str,float])` in both T7 def and T9 wiring; `Horizon.value` is the day count everywhere.
- [ ] Scope holds: no portfolio construction / sizing / real-money.
```
