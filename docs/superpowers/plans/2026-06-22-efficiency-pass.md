# Efficiency Pass Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Eliminate double-mypy in `make check`, decompose `sqlite_store.py` (1093 LOC) and `stock_analyzer.py` (1305 LOC) into focused packages, and add quiet flag to `make test`.

**Architecture:** Three independent changes. Makefile fix is one line. Both decompositions use the façade pattern — the original import path (`from adapters.data.sqlite_store import SQLiteStore`, `from adapters.visualization.stock_analyzer import analyze_ticker`) keeps working via a thin re-export shim, so zero callers change. Tests for sqlite_store are split into per-module files.

**Tech Stack:** Python 3.12, sqlite3 stdlib, pytest + pytest-xdist, mypy strict, make.

---

## Task 1: Fix double mypy + `make test` quiet flag

**Files:**
- Modify: `Makefile`

- [ ] **Step 1: Verify mypy version parity**

```bash
uv run mypy --version
grep "rev:" .pre-commit-config.yaml | grep mypy
```

Expected: both show `1.8.x`. If they differ, bump `.pre-commit-config.yaml` `rev` to match installed version before continuing.

- [ ] **Step 2: Edit Makefile**

In `Makefile`, make two changes:

```makefile
# Line ~37 — remove typecheck from check chain
check: lint test-cov

# Line ~27 — add -q to test target
test:
	$(PYTEST) tests/ -q -n auto --tb=short
```

`make typecheck` target stays intact as a standalone command. Only remove it from the `check` dependency chain.

- [ ] **Step 3: Verify `make check` runs mypy only once**

```bash
make check 2>&1 | grep -c "mypy"
```

Expected: `1` (from pre-commit), not `2`.

- [ ] **Step 4: Commit**

```bash
git add Makefile
git commit -m "chore: remove double mypy from make check; add -q to make test"
```

---

## Task 2: Decompose `sqlite_store.py` — base + schema

**Files:**
- Create: `adapters/data/store/__init__.py`
- Create: `adapters/data/store/_base.py`

- [ ] **Step 1: Read the full `sqlite_store.py`**

```bash
cat adapters/data/sqlite_store.py
```

Understand: `_to_naive_utc` helper, `_SCHEMA` string (all CREATE TABLE statements), `SQLiteStore.__init__` (connects + runs schema), `SQLiteStore._connect`.

- [ ] **Step 2: Create `adapters/data/store/_base.py`**

Extract the shared utilities into this file:

```python
"""Shared SQLite helpers for all store sub-modules."""

from __future__ import annotations

import sqlite3
from datetime import datetime, timezone


def to_naive_utc(dt: datetime) -> datetime:
    if dt.tzinfo is not None:
        return dt.astimezone(timezone.utc).replace(tzinfo=None)
    return dt


_SCHEMA = """
<paste the full _SCHEMA string from sqlite_store.py here verbatim>
"""


def connect_and_init(db_path: str) -> sqlite3.Connection:
    conn = sqlite3.connect(db_path)
    conn.executescript(_SCHEMA)
    return conn
```

- [ ] **Step 3: Create empty `adapters/data/store/__init__.py`** (populated in Task 10)

```python
"""SQLite store package — re-exports SQLiteStore for backward compatibility."""
```

- [ ] **Step 4: Run typecheck to verify clean**

```bash
make typecheck
```

Expected: no errors in `adapters/data/store/`.

---

## Task 3: Extract `store/recommendations.py`

**Files:**
- Create: `adapters/data/store/recommendations.py`

- [ ] **Step 1: Create `adapters/data/store/recommendations.py`**

```python
from __future__ import annotations

import json
import sqlite3
from datetime import datetime

from domain.models import MultiHorizonPrediction, RecommendationGrade, StockRecommendation

from adapters.data.store._base import connect_and_init, to_naive_utc


class RecommendationsMixin:
    _db_path: str

    def _conn(self) -> sqlite3.Connection:
        return connect_and_init(self._db_path)

    def save_recommendation(self, rec: StockRecommendation) -> None:
        # paste save_recommendation body from sqlite_store.py verbatim
        ...

    def get_recommendations(
        self,
        symbol: str | None = None,
        limit: int = 100,
    ) -> list[StockRecommendation]:
        # paste get_recommendations body from sqlite_store.py verbatim
        ...
```

Copy the method bodies exactly from `sqlite_store.py`. Replace `self._connect()` calls with `self._conn()`. Replace `_to_naive_utc(` with `to_naive_utc(`.

- [ ] **Step 2: Run typecheck**

```bash
uv run mypy adapters/data/store/recommendations.py --strict
```

Fix any type errors before continuing.

---

## Task 4: Extract remaining store sub-modules

**Files:**
- Create: `adapters/data/store/accuracy.py`
- Create: `adapters/data/store/evaluation.py`
- Create: `adapters/data/store/weekly_reports.py`
- Create: `adapters/data/store/buzz_signals.py`
- Create: `adapters/data/store/source_reliability.py`
- Create: `adapters/data/store/holdings.py`
- Create: `adapters/data/store/trades.py`

- [ ] **Step 1: Create `store/accuracy.py`**

Same Mixin pattern as Task 3. Methods to move:
- `save_accuracy_record`
- `get_accuracy_records`

Imports needed: `domain.models.AccuracyRecord`. Replace `_to_naive_utc` with `to_naive_utc`.

- [ ] **Step 2: Create `store/evaluation.py`**

Methods: `save_evaluation_run`, `get_evaluation_runs`.
Imports: `domain.models.EvaluationRun`.

- [ ] **Step 3: Create `store/weekly_reports.py`**

Methods: `save_weekly_report`, `get_weekly_report`.
Imports: `domain.models.WeeklyReport`.

- [ ] **Step 4: Create `store/buzz_signals.py`**

Methods: `save_buzz_signal`, `get_buzz_signals`.
Imports: `domain.models.BuzzSignal`.

- [ ] **Step 5: Create `store/source_reliability.py`**

Methods: `record_source_outcome`, `get_source_reliability`, `get_all_source_reliabilities`.
Imports: `domain.models.SourceReliability`.

- [ ] **Step 6: Create `store/holdings.py`**

Methods: `add_holding`, `remove_holding`, `get_holdings`, `get_holding`, `add_watchlist`, `remove_watchlist`, `get_watchlist`.
Imports: `domain.models.Holding`.

- [ ] **Step 7: Create `store/trades.py`**

Methods: `save_trade`, `get_trades`, `save_trade_outcome`, `get_trade_outcomes`.
Imports: `domain.outcome.TrackedTrade, TradeAction, TradeOutcome`.

- [ ] **Step 8: Run typecheck on all new modules**

```bash
uv run mypy adapters/data/store/ --strict
```

Fix all errors before continuing.

---

## Task 5: Assemble façade in `store/__init__.py`

**Files:**
- Modify: `adapters/data/store/__init__.py`

- [ ] **Step 1: Write the composed façade**

```python
"""SQLite store package — re-exports SQLiteStore for backward compatibility."""

from __future__ import annotations

from adapters.data.store._base import connect_and_init, to_naive_utc
from adapters.data.store.accuracy import AccuracyMixin
from adapters.data.store.buzz_signals import BuzzSignalsMixin
from adapters.data.store.evaluation import EvaluationMixin
from adapters.data.store.holdings import HoldingsMixin
from adapters.data.store.recommendations import RecommendationsMixin
from adapters.data.store.source_reliability import SourceReliabilityMixin
from adapters.data.store.trades import TradesMixin
from adapters.data.store.weekly_reports import WeeklyReportsMixin


class SQLiteStore(
    RecommendationsMixin,
    AccuracyMixin,
    EvaluationMixin,
    WeeklyReportsMixin,
    BuzzSignalsMixin,
    SourceReliabilityMixin,
    HoldingsMixin,
    TradesMixin,
):
    def __init__(self, db_path: str = "data/recommendations.db") -> None:
        self._db_path = db_path
        conn = connect_and_init(db_path)
        conn.close()


__all__ = ["SQLiteStore"]
```

- [ ] **Step 2: Run typecheck**

```bash
uv run mypy adapters/data/store/ --strict
```

Expected: clean.

---

## Task 6: Replace `sqlite_store.py` with re-export shim

**Files:**
- Modify: `adapters/data/sqlite_store.py`

- [ ] **Step 1: Replace entire file with shim**

```python
"""Backward-compatibility shim — SQLiteStore moved to adapters.data.store."""

from adapters.data.store import SQLiteStore

__all__ = ["SQLiteStore"]
```

- [ ] **Step 2: Verify original import path still works**

```bash
uv run python -c "from adapters.data.sqlite_store import SQLiteStore; print(SQLiteStore)"
```

Expected: `<class 'adapters.data.store.SQLiteStore'>` — no ImportError.

- [ ] **Step 3: Run full test suite**

```bash
make test-fast
```

Expected: same pass count as before (≥2200). Any failure = a caller broke; fix before committing.

- [ ] **Step 4: Run typecheck**

```bash
make typecheck
```

Expected: clean.

- [ ] **Step 5: Split `tests/test_sqlite_store.py` into per-module test files**

Create `tests/adapters/store/` directory. Move each test class/function to the file matching its domain:

- `tests/adapters/store/test_recommendations.py` — tests for `save_recommendation`, `get_recommendations`
- `tests/adapters/store/test_accuracy.py` — tests for accuracy methods
- `tests/adapters/store/test_evaluation.py` — tests for evaluation run methods
- `tests/adapters/store/test_weekly_reports.py` — tests for weekly report methods
- `tests/adapters/store/test_buzz_signals.py` — tests for buzz signal methods
- `tests/adapters/store/test_source_reliability.py` — tests for source reliability methods
- `tests/adapters/store/test_holdings.py` — tests for holding/watchlist methods
- `tests/adapters/store/test_trades.py` — tests for trade/outcome methods

Each test file imports `SQLiteStore` via the shim: `from adapters.data.sqlite_store import SQLiteStore`.
Delete the original `tests/test_sqlite_store.py` after all tests are moved.

- [ ] **Step 6: Run test suite again to confirm test split is clean**

```bash
make test-fast
```

Expected: same pass count. No tests lost.

- [ ] **Step 7: Commit**

```bash
git add adapters/data/store/ adapters/data/sqlite_store.py tests/adapters/store/ tests/test_sqlite_store.py
git commit -m "refactor: decompose sqlite_store.py into store/ package (facade preserves import path)"
```

---

## Task 7: Decompose `stock_analyzer.py` — models + loaders

**Files:**
- Create: `adapters/visualization/analysis/__init__.py`
- Create: `adapters/visualization/analysis/models.py`
- Create: `adapters/visualization/analysis/loaders.py`
- Create: `adapters/visualization/analysis/scoring/__init__.py`

- [ ] **Step 1: Create `analysis/models.py`**

Extract `SectionScore` and `AnalysisResult` dataclasses (lines 22–88 of `stock_analyzer.py`):

```python
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class SectionScore:
    # paste exact fields from stock_analyzer.py
    ...


@dataclass
class AnalysisResult:
    # paste exact fields from stock_analyzer.py
    ...
```

- [ ] **Step 2: Create `analysis/loaders.py`**

Extract `_load_buzz_signals`, `_load_recommendation`, `_get_sector_peers` (lines 1147–1258):

```python
from __future__ import annotations

from typing import Any

from adapters.visualization.analysis.models import AnalysisResult


def load_buzz_signals(ticker: str, db_path: str) -> list[Any]:
    # paste _load_buzz_signals body verbatim
    ...

def load_recommendation(ticker: str, db_path: str) -> Any:
    # paste _load_recommendation body verbatim
    ...

def get_sector_peers(ticker: str, sector: str, db_path: str) -> list[dict[str, Any]]:
    # paste _get_sector_peers body verbatim
    ...
```

- [ ] **Step 3: Create empty `analysis/scoring/__init__.py`**

```python
"""Scorer sub-modules for stock analysis."""
```

- [ ] **Step 4: Create empty `analysis/__init__.py`** (populated in Task 9)

```python
"""Stock analysis package."""
```

- [ ] **Step 5: Run typecheck**

```bash
uv run mypy adapters/visualization/analysis/ --strict
```

---

## Task 8: Extract scoring sub-modules

**Files:**
- Create: `adapters/visualization/analysis/scoring/valuation.py`
- Create: `adapters/visualization/analysis/scoring/growth.py`
- Create: `adapters/visualization/analysis/scoring/performance.py`
- Create: `adapters/visualization/analysis/scoring/health.py`
- Create: `adapters/visualization/analysis/scoring/ownership.py`
- Create: `adapters/visualization/analysis/scoring/sentiment.py`
- Create: `adapters/visualization/analysis/scoring/supply_chain.py`
- Create: `adapters/visualization/analysis/radar.py`

Each scoring module follows this pattern:

```python
from __future__ import annotations

from typing import Any

from adapters.visualization.analysis.models import SectionScore


def score_<domain>(info: dict[str, Any], ...) -> SectionScore:
    # paste _score_<domain> body verbatim, rename private → public
    ...
```

- [ ] **Step 1: Create `scoring/valuation.py`** — extract `_score_valuation` + `_sector_pe_avg` (lines 271–405). Rename to `score_valuation`, `sector_pe_avg`.

- [ ] **Step 2: Create `scoring/growth.py`** — extract `_score_growth` (lines 407–508). Rename to `score_growth`.

- [ ] **Step 3: Create `scoring/performance.py`** — extract `_score_performance` (lines 510–606). Rename to `score_performance`.

- [ ] **Step 4: Create `scoring/health.py`** — extract `_score_health` (lines 608–737). Rename to `score_health`.

- [ ] **Step 5: Create `scoring/ownership.py`** — extract `_score_ownership` (lines 739–860). Rename to `score_ownership`.

- [ ] **Step 6: Create `scoring/sentiment.py`** — extract `_score_sentiment` (lines 862–964). Rename to `score_sentiment`.

- [ ] **Step 7: Create `scoring/supply_chain.py`** — extract `_score_supply_chain` + `_find_supply_chain_group` (lines 966–1052). Rename to `score_supply_chain`, `find_supply_chain_group`.

- [ ] **Step 8: Create `radar.py`** — extract `_compute_signal_radar` + `aggregate_insider_by_quarter` (lines 1054–1178). Rename to `compute_signal_radar`, `aggregate_insider_by_quarter`.

- [ ] **Step 9: Run typecheck on all scoring modules**

```bash
uv run mypy adapters/visualization/analysis/ --strict
```

Fix all errors.

---

## Task 9: Assemble orchestrator + façade

**Files:**
- Create: `adapters/visualization/analysis/analyze.py`
- Modify: `adapters/visualization/analysis/__init__.py`

- [ ] **Step 1: Create `analysis/analyze.py`**

Extract `analyze_ticker` (lines 90–269), updating all internal calls to use imported module functions:

```python
from __future__ import annotations

from typing import Any

from adapters.visualization.analysis.loaders import (
    find_supply_chain_group,
    get_sector_peers,
    load_buzz_signals,
    load_recommendation,
)
from adapters.visualization.analysis.models import AnalysisResult
from adapters.visualization.analysis.radar import compute_signal_radar
from adapters.visualization.analysis.scoring.growth import score_growth
from adapters.visualization.analysis.scoring.health import score_health
from adapters.visualization.analysis.scoring.ownership import score_ownership
from adapters.visualization.analysis.scoring.performance import score_performance
from adapters.visualization.analysis.scoring.sentiment import score_sentiment
from adapters.visualization.analysis.scoring.supply_chain import score_supply_chain
from adapters.visualization.analysis.scoring.valuation import score_valuation


def analyze_ticker(
    ticker: str,
    db_path: str = "data/recommendations.db",
    peers: list[dict[str, Any]] | None = None,
) -> AnalysisResult:
    # paste analyze_ticker body verbatim, replacing _score_* calls with score_* imports
    ...
```

- [ ] **Step 2: Update `analysis/__init__.py`**

```python
"""Stock analysis package — re-exports public API."""

from adapters.visualization.analysis.analyze import analyze_ticker
from adapters.visualization.analysis.models import AnalysisResult, SectionScore

__all__ = ["analyze_ticker", "AnalysisResult", "SectionScore"]
```

- [ ] **Step 3: Run typecheck**

```bash
uv run mypy adapters/visualization/analysis/ --strict
```

---

## Task 10: Replace `stock_analyzer.py` with re-export shim

**Files:**
- Modify: `adapters/visualization/stock_analyzer.py`

- [ ] **Step 1: Replace file with shim**

```python
"""Backward-compatibility shim — moved to adapters.visualization.analysis."""

from adapters.visualization.analysis import AnalysisResult, SectionScore, analyze_ticker
from adapters.visualization.analysis.radar import aggregate_insider_by_quarter

__all__ = ["analyze_ticker", "AnalysisResult", "SectionScore", "aggregate_insider_by_quarter"]
```

- [ ] **Step 2: Verify original import path works**

```bash
uv run python -c "from adapters.visualization.stock_analyzer import analyze_ticker; print(analyze_ticker)"
```

Expected: no ImportError.

- [ ] **Step 3: Run full test suite**

```bash
make test-fast
```

Expected: same pass count as before. Any failure = a caller reference broke; fix it.

- [ ] **Step 4: Run typecheck**

```bash
make typecheck
```

Expected: clean.

- [ ] **Step 5: Commit**

```bash
git add adapters/visualization/analysis/ adapters/visualization/stock_analyzer.py
git commit -m "refactor: decompose stock_analyzer.py into analysis/ package (facade preserves import path)"
```

---

## Task 11: Full gate + final verification

- [ ] **Step 1: Run full gate**

```bash
make check
```

Confirm: lint passes, mypy runs once only, test-cov passes ≥90%, no regressions.

- [ ] **Step 2: Verify import paths end-to-end**

```bash
uv run python -c "
from adapters.data.sqlite_store import SQLiteStore
from adapters.visualization.stock_analyzer import analyze_ticker
from adapters.visualization.analysis import AnalysisResult
print('all imports OK')
"
```

- [ ] **Step 3: Final commit if anything outstanding**

```bash
git add -u
git commit -m "chore: efficiency pass complete — ADR-061 closed"
```

---

## Branch + PR

```bash
# Work on:
git checkout -b feat/efficiency-pass develop

# PR to develop after make check passes locally (no CI wait — Actions minutes exhausted)
```
