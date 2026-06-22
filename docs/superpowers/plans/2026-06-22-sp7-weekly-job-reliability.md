# Plan — SP7: Weekly Job Reliability
_Date: 2026-06-22 | Brief: docs/superpowers/specs/2026-06-20-sp7-weekly-job-reliability-brief.md_
_No full spec needed — three independent bugfixes with known solutions._

## Tasks

### Task 1 — Fix `holdings_risk.py` numpy-float crash (HIGH)

**File:** `application/holdings_risk.py:61`
**Symptom:** `statistics.pstdev(tail)` raises `AttributeError: 'float' object has no attribute 'numerator'`
when `tail` contains numpy floats (Python 3.12 stdlib incompatibility).

**Fix:**
```python
# Before (line 61)
return statistics.pstdev(tail) if len(tail) >= 2 else 0.0

# After
return statistics.pstdev([float(x) for x in tail]) if len(tail) >= 2 else 0.0
```

**Also audit:** grep `statistics\.` across `application/` and `domain/` for any other call that
receives numpy floats. Fix same pattern wherever found.

**Test:** Add to `tests/test_holdings_risk.py` — fixture with numpy-float returns list:
```python
import numpy as np
returns = [np.float64(0.01), np.float64(-0.02), np.float64(0.03)]
result = compute_tail_risk(returns)   # must not raise
assert isinstance(result, float)
```

**Gate:** `pytest tests/test_holdings_risk.py -q` passes.

---

### Task 2 — Make `run-tournament` fail loud (MED)

**File:** `application/use_cases.py` (`WeeklyTournamentUseCase.execute`) +
`application/cli/ml_commands.py` (exit code)

**Symptom:** Unfitted predictor → `NotFittedError` swallowed → 0 picks → exit 0 (silent success).

**Fix:**
1. In `WeeklyTournamentUseCase.execute`: detect unfitted predictors before running. If none fitted,
   raise `RuntimeError("No trained model available — run 'fit' first. Tournament is a no-op.")`.
2. In CLI handler: catch `RuntimeError` from tournament → `sys.exit(1)` with the message printed.
3. Do NOT swallow, retry, or revive the prediction ensemble.

**Test:** Add to `tests/test_backtest_runner.py` or new `tests/test_tournament_no_model.py`:
```python
def test_tournament_raises_when_no_model_fitted(fake_store, fake_predictor_unfitted):
    uc = WeeklyTournamentUseCase(predictor=fake_predictor_unfitted, store=fake_store)
    with pytest.raises(RuntimeError, match="no trained model"):
        uc.execute()
```

**Gate:** `pytest tests/test_backtest_runner.py tests/test_tournament_no_model.py -q` passes.

---

### Task 3 — Wire `corroborate` into weekly cadence (LOW)

**Depends on:** SP1 merged to develop (PR #73).

**File:** scheduler config (launchd plist or equivalent weekly script).

**Fix:** After SP1 merges, add two steps to the weekly scheduled job:
1. `python -m application.cli corroborate` — runs corroboration sweep
2. `python -m application.cli resolve-corroboration` — resolves forward returns (SP5 wires this
   fully; this task just adds the CLI hook placeholder)

**Note:** Task 3 is blocked on PR #73 merge. Implement Tasks 1 and 2 first on an independent
branch. Task 3 can be a follow-up commit once #73 lands.

---

## Branch strategy

```
feat/sp7-weekly-reliability  (off develop, after PR drain)
├── Task 1: holdings_risk fix + test
├── Task 2: tournament fail-loud + test
└── Task 3: weekly cadence wire (after #73 merges)
```

## Gate sequence

```
After Task 1:  pytest tests/test_holdings_risk.py -q
After Task 2:  pytest tests/test_backtest_runner.py tests/test_tournament_no_model.py -q
After Task 3:  make test-fast  (full suite)
Pre-PR:        make check
```

## Definition of done

- [ ] `weekly-brief` no longer crashes on numpy-float returns
- [ ] `run-tournament` exits non-zero with clear message when no model fitted
- [ ] `corroborate` wired into weekly job (or stub committed with TODO: unblock on #73)
- [ ] `make check` passes locally
- [ ] PR to develop, no CI wait (Actions minutes exhausted)
