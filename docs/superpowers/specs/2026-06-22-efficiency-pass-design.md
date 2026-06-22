# Spec — Efficiency Pass (ADR-061 Close-Out)
_Date: 2026-06-22 | Status: approved, ready for plan_

## Context

Research doc `research/2026-06-22-efficiency-bottleneck-audit.md` found that xdist, quiet flags,
timeout guards, tab markers, and cli/risk decomposition are **already done**. Three real bottlenecks
remain. This spec closes ADR-061.

---

## Bottleneck 1 — Double Mypy in `make check`

### What
`Makefile` `check` target runs `lint` (pre-commit, includes mypy strict) then `typecheck`
(standalone mypy strict). mypy executes twice. Wasted ~30–60s every full gate.

### Fix
Remove `typecheck` from `check` target:
```makefile
# Before
check: lint typecheck test-cov

# After
check: lint test-cov
```

`make typecheck` target stays as a standalone command for deliberate type-only runs. Just remove
it from the `check` chain.

### Risk mitigation
Pre-commit mypy pins `rev: v1.8.0` (`.pre-commit-config.yaml:32`). Verify installed mypy version
matches before removing standalone step. If they diverge, bump pin first, then remove from `check`.

---

## Bottleneck 2 — `sqlite_store.py` Decomposition

### What
`adapters/data/sqlite_store.py` (1093 LOC) is a single `SQLiteStore` class managing 8 unrelated
domain objects. Every AI edit to any persistence concern reads the whole file.

### Decomposition boundaries

Split into a package `adapters/data/store/` with one module per domain object group:

| Module | Methods | Lines (approx) |
|--------|---------|----------------|
| `store/recommendations.py` | `save_recommendation`, `get_recommendations` | ~50 |
| `store/accuracy.py` | `save_accuracy_record`, `get_accuracy_records` | ~60 |
| `store/evaluation.py` | `save_evaluation_run`, `get_evaluation_runs` | ~50 |
| `store/weekly_reports.py` | `save_weekly_report`, `get_weekly_report` | ~45 |
| `store/buzz_signals.py` | `save_buzz_signal`, `get_buzz_signals` | ~55 |
| `store/source_reliability.py` | `record_source_outcome`, `get_source_reliability`, `get_all_source_reliabilities` | ~60 |
| `store/holdings.py` | `add_holding`, `remove_holding`, `get_holdings`, `get_holding`, `add_watchlist`, `remove_watchlist`, `get_watchlist` | ~85 |
| `store/trades.py` | `save_trade`, `get_trades`, `save_trade_outcome`, `get_trade_outcomes` | ~70 |
| `store/_base.py` | `_to_naive_utc`, `_connect`, shared schema init helpers | ~50 |
| `store/__init__.py` | Re-exports `SQLiteStore` composed from all sub-stores | ~30 |

`SQLiteStore` becomes a thin façade in `__init__.py` that composes the sub-stores and exposes the
same public API — zero callers change.

### Key constraint
`SQLiteStore` is imported by many callers via `from adapters.data.sqlite_store import SQLiteStore`.
The `__init__.py` must re-export `SQLiteStore` so that import path stays valid, OR update all
callers. Prefer re-export (zero caller churn).

### Tests
`tests/test_sqlite_store.py` exists at root tests/ level. After decomposition, split into
`tests/adapters/store/test_*.py` per module. All existing tests must pass unchanged in behaviour.

---

## Bottleneck 3 — `stock_analyzer.py` Decomposition

### What
`adapters/visualization/stock_analyzer.py` (1305 LOC) contains 7 independent scoring functions
plus an orchestrator `analyze_ticker`. Excluded from coverage. AI reads whole file to edit one
scorer.

### Decomposition boundaries

Split into a package `adapters/visualization/analysis/`:

| Module | Content | Lines (approx) |
|--------|---------|----------------|
| `analysis/models.py` | `SectionScore`, `AnalysisResult` dataclasses | ~35 |
| `analysis/scoring/valuation.py` | `_score_valuation`, `_sector_pe_avg` | ~140 |
| `analysis/scoring/growth.py` | `_score_growth` | ~105 |
| `analysis/scoring/performance.py` | `_score_performance` | ~100 |
| `analysis/scoring/health.py` | `_score_health` | ~130 |
| `analysis/scoring/ownership.py` | `_score_ownership` | ~125 |
| `analysis/scoring/sentiment.py` | `_score_sentiment` | ~105 |
| `analysis/scoring/supply_chain.py` | `_score_supply_chain`, `_find_supply_chain_group` | ~95 |
| `analysis/radar.py` | `_compute_signal_radar`, `aggregate_insider_by_quarter` | ~110 |
| `analysis/loaders.py` | `_load_buzz_signals`, `_load_recommendation`, `_get_sector_peers` | ~70 |
| `analysis/analyze.py` | `analyze_ticker` orchestrator (calls all scorers) | ~185 |
| `analysis/__init__.py` | Re-exports `analyze_ticker`, `AnalysisResult` | ~10 |

Callers import `from adapters.visualization.stock_analyzer import analyze_ticker`. The `__init__.py`
re-exports it — zero caller churn.

### Tests
`adapters/visualization/` is excluded from coverage. No existing unit tests for scorers. Do NOT add
tests in this pass — scope is decomposition only. Tests are a separate future task.

---

## Minor Fix — `make test` Quiet Flag

Add `-q` to the `test` target for consistency with all other targets:

```makefile
# Before
test:
    $(PYTEST) tests/ -n auto --tb=short

# After
test:
    $(PYTEST) tests/ -q -n auto --tb=short
```

---

## Out of Scope

- Coverage exclusion list cleanup (quality gap, not efficiency — separate ADR)
- Screenshot verification cost (no harness exists yet)
- Adding tests to visualization adapters
- Any change to `domain/`, `application/`, or test logic

---

## Verification

After each decomposition:
1. `make test-fast` — full suite passes
2. `make typecheck` — mypy strict clean
3. `from adapters.data.sqlite_store import SQLiteStore` — import resolves
4. `from adapters.visualization.stock_analyzer import analyze_ticker` — import resolves
5. `make check` — full gate passes (now without double mypy)

---

## Files touched

```
Makefile                                         (double-mypy fix + test quiet)
adapters/data/sqlite_store.py                    (replaced by package)
adapters/data/store/__init__.py                  (new — façade)
adapters/data/store/_base.py                     (new)
adapters/data/store/recommendations.py           (new)
adapters/data/store/accuracy.py                  (new)
adapters/data/store/evaluation.py                (new)
adapters/data/store/weekly_reports.py            (new)
adapters/data/store/buzz_signals.py              (new)
adapters/data/store/source_reliability.py        (new)
adapters/data/store/holdings.py                  (new)
adapters/data/store/trades.py                    (new)
adapters/visualization/stock_analyzer.py         (replaced by package)
adapters/visualization/analysis/__init__.py      (new — façade)
adapters/visualization/analysis/models.py        (new)
adapters/visualization/analysis/analyze.py       (new)
adapters/visualization/analysis/radar.py         (new)
adapters/visualization/analysis/loaders.py       (new)
adapters/visualization/analysis/scoring/valuation.py    (new)
adapters/visualization/analysis/scoring/growth.py       (new)
adapters/visualization/analysis/scoring/performance.py  (new)
adapters/visualization/analysis/scoring/health.py       (new)
adapters/visualization/analysis/scoring/ownership.py    (new)
adapters/visualization/analysis/scoring/sentiment.py    (new)
adapters/visualization/analysis/scoring/supply_chain.py (new)
tests/adapters/store/test_*.py                   (split from tests/test_sqlite_store.py)
```
