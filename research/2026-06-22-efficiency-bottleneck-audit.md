# Efficiency Bottleneck Audit — ADR-061
_Date: 2026-06-22 | Scope: test suite, Makefile, module size, coverage_

## Summary

xdist parallelism, quiet flags, timeout guards, tab markers, and cli/risk module decomposition are **already done**. Three real bottlenecks remain: (1) double mypy in `make check` wastes ~30–60s every full gate run; (2) five source modules between 1000–1524 LOC hurt AI navigability and token cost; (3) coverage exclusions are too broad — ~7000+ LOC of visualization + all CLI omitted, so the 90% threshold only measures a subset of the codebase.

---

## 1. Already-Resolved Bottlenecks (do not re-address)

| Item | Where fixed | Evidence |
|------|-------------|----------|
| xdist parallelism | All Makefile targets | `-n auto` on `test-fast`, `test-tab`, `test-domain`, `test-adapters`, `test-smoke`, `test`, `test-cov` |
| Quiet default output | `test-fast`, `test-tab`, etc. | `-q` flag present |
| Timeout guard | `pyproject.toml:addopts` | `--timeout=90 --timeout-method=thread` |
| Tab markers auto-applied | `tests/conftest.py:38-58` | `pytest_collection_modifyitems` auto-tags 6 tabs |
| CLI decomposition | `application/cli/` package | `_cli_group.py`, `_deps.py`, `*_commands.py` |
| Risk tab decomposition | `adapters/visualization/tabs/risk/` | `compose.py`, `components.py`, `evidence.py`, `factor_chart.py`, `enb_section.py`, `sections.py` |
| API key leakage guard | `tests/conftest.py:17-21` | autouse `_strip_live_api_keys` fixture |

---

## 2. Real Bottleneck: Double Mypy in `make check`

**File:** `Makefile:37`
```makefile
check: lint typecheck test-cov
```

- `lint` = `pre-commit run --all-files` → runs mypy strict via `.pre-commit-config.yaml:32-43`
- `typecheck` = `uv run mypy domain/ adapters/ application/ --strict`

mypy runs **twice** on every `make check`. mypy is the slowest pre-commit hook. Estimated waste: 30–60s per full gate.

**Fix:** Remove `typecheck` from `check` target. `lint` already covers it.

**Risk:** Pre-commit mypy in `.pre-commit-config.yaml` pins `rev: v1.8.0`. Standalone `make typecheck` uses installed version (potentially newer). If versions diverge, removing the standalone step could miss drift. Verify pinned version matches installed before removing.

---

## 3. Real Bottleneck: Oversized Source Modules

Modules >800 LOC that are not yet decomposed (from `wc -l` over source tree):

| File | LOC | Domain | Notes |
|------|-----|--------|-------|
| `adapters/visualization/components/styles.py` | 1524 | UI styling | CSS/HTML string constants — hard to split semantically |
| `adapters/visualization/stock_analyzer.py` | 1305 | Analysis | 7 scoring functions + aggregation; clear split boundaries |
| `adapters/visualization/tabs/research_candidates.py` | 1211 | Visualization | Single-file tab, large rendering logic |
| `adapters/data/sqlite_store.py` | 1093 | Persistence | 30+ methods across 8 domain objects (see §3.1) |
| `adapters/visualization/tabs/stock_analysis.py` | 1055 | Visualization | Single-file tab |

### 3.1 `sqlite_store.py` — decomposition boundaries (highest priority)

`SQLiteStore` class at `adapters/data/sqlite_store.py:281` manages 8 distinct domain objects with no internal cohesion:

- Recommendations (`save_recommendation`, `get_recommendations`) — lines 289–338
- Accuracy records (`save_accuracy_record`, `get_accuracy_records`) — lines 340–396
- Evaluation runs (`save_evaluation_run`, `get_evaluation_runs`) — lines 398–444
- Weekly reports (`save_weekly_report`, `get_weekly_report`) — lines 446–486
- Buzz signals (`save_buzz_signal`, `get_buzz_signals`) — lines 487–538
- Source reliability (`record_source_outcome`, `get_source_reliability`, `get_all_source_reliabilities`) — lines 540–598
- Holdings + watchlist (`add_holding`, `remove_holding`, `get_holdings`, `get_holding`, `add_watchlist`, `remove_watchlist`, `get_watchlist`) — lines 600–680
- Trades + outcomes (`save_trade`, `get_trades`, `save_trade_outcome`, `get_trade_outcomes`) — lines 682–749

Test file: `tests/test_sqlite_store.py` (exists in root tests/, not tests/adapters/).

### 3.2 `stock_analyzer.py` — decomposition boundaries

7 scoring functions with clear separation:

- `_score_valuation` (lines 271–405) — valuation ratios vs peers
- `_score_growth` (lines 407–508) — revenue/earnings growth
- `_score_performance` (lines 510–606) — price performance
- `_score_health` (lines 608–737) — balance sheet health
- `_score_ownership` (lines 739–860) — institutional/insider
- `_score_sentiment` (lines 862–964) — buzz signals
- `_score_supply_chain` (lines 966–1052) — supply chain group

Orchestrator `analyze_ticker` (lines 90–269) calls all 7. Natural split: `scorer_*.py` modules + `analyze.py` orchestrator.

---

## 4. Coverage Gap: Exclusion List Too Broad

**File:** `pyproject.toml:[tool.coverage.run]` and `[tool.coverage.report]`

Excluded from coverage enforcement:
```
application/cli/*.py          # entire CLI package
adapters/visualization/*      # entire dashboard (~7 files, >6000 LOC)
adapters/data/yfinance_adapter.py
adapters/ml/gemini_event_classifier.py
application/backtest_runner.py
application/shap_analysis.py
application/use_cases.py      # 706 LOC excluded
application/validate_phase3b.py
```

The 90% threshold (`--cov-fail-under=90`) only applies to the non-excluded subset. A regression in any excluded module would pass CI undetected.

Note: `adapters/visualization/*` tests DO exist (e.g. `test_risk_tab.py`, `test_weekly_brief_tab.py`) but they run without coverage counting. Adding them to coverage would require either lowering the threshold or writing more assertions.

---

## 5. Minor: `make test` target lacks `-q`

**File:** `Makefile:27`
```makefile
test:
    $(PYTEST) tests/ -n auto --tb=short
```

No `-q` flag. Produces verbose output when run. `test-fast` has `-q`. Low priority since `test-fast` is the recommended iteration target.

---

## 6. Non-Bottleneck: Screenshot Verification

ADR-061 listed screenshot verification cost. No screenshot harness found in source tree. This appears to be a forward-looking concern, not a present bottleneck.

---

## Cross-Component Notes

- All network-adjacent tests inject fakes (`http_get`, `sleep=lambda`) or use `tests/fakes/` port doubles — no real network calls found in test suite.
- `tests/fakes/` has 16 fake adapters covering all major ports.
- `tmp_path` used for all file/DB tests → xdist-safe (no shared state).
