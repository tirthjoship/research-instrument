# Spec Brief — SP7: Weekly Job Reliability

**Status:** Design brief (mostly bugfix + hardening; smaller than others)
**Depends on:** none (can run independently / first)
**Date:** 2026-06-20

## Purpose
Both weekly jobs are currently broken or misleading. Fix them so the weekly cadence is trustworthy before
layering corroboration on top.

## Three independent fixes
1. **`weekly-brief` crash (HIGH).** `application/holdings_risk.py:61` — `statistics.pstdev(tail)` raises
   `AttributeError: 'float' object has no attribute 'numerator'` when fed numpy floats (Python 3.12
   stdlib incompatibility). Fix: cast to `float()` / use a numpy-or-pure stdev that accepts numpy floats.
   TDD with a fixture of numpy-float returns.
2. **`run-tournament` silent 0-picks (MED).** Dead ML path (no model loaded → `NotFittedError` swallowed
   → 0 picks, exit 0). Make it **fail loud**: detect unfitted predictors and exit non-zero with
   "no trained model — run is a no-op" instead of pretending success. (Do NOT revive the model — see
   `project_run_tournament_dead_path`.)
3. **Wire `corroborate` into the weekly cadence (LOW).** Once SP1 lands, add the weekly `corroborate` +
   `resolve-corroboration` (SP5) to the scheduled jobs alongside the discipline review.

## Scope (out)
- Reviving the prediction ensemble (only SP5/Hypothesis #9 could justify).

## Files likely touched
`application/holdings_risk.py` (fix), `tests/test_holdings_risk.py` (add numpy-float case),
`application/use_cases.py` (fail-loud guard in `WeeklyTournamentUseCase.execute`),
`application/cli/ml_commands.py` (exit code), scheduler config.

## Open questions
- Fix #1: cleanest stdev (propose `float(np.std(tail))` or coerce list to `[float(x) for x in tail]`
  before `statistics.pstdev`). Verify no other `statistics.*` call has the same numpy-float exposure.
- Fix #2: fail-loud vs hide the command — propose fail-loud (most honest).
