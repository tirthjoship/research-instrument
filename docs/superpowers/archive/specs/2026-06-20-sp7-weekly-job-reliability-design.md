# SP7 Design — Weekly Job Reliability

**Status:** Draft for user review
**Date:** 2026-06-20
**Branch:** `feat/corroboration-engine`
**Depends on:** none for fixes; SP1 for the optional corroboration cadence slot
**Supersedes brief:** `docs/superpowers/specs/2026-06-20-sp7-weekly-job-reliability-brief.md`

## Decision

Build SP7 first. It is the reliability gate before the corroboration consumers:

1. SP7 weekly-job reliability
2. SP2 candidate surfacing
3. SP3 screener revamp
4. SP4 portfolio-verdict integration
5. SP5 Hypothesis #9 forward gate
6. SP6 stock-analysis tabs

This order keeps the weekly cadence honest before new tickers, screener ranking, portfolio guidance, validation, or dashboard UI depend on it.

## Context

SP1 built the corroboration engine and proved the live path, but the project still has two weekly-cadence problems:

- `weekly-brief` can crash inside `application/holdings_risk.py` when `statistics.pstdev()` receives numpy scalar returns under Python 3.12.
- `run-tournament` is a legacy prediction path that can silently produce zero picks because predictors are not trained or loaded, then still exit successfully.

There is also a nearby reliability risk: `application/discipline_backtest.py` uses the same `statistics.pstdev()` pattern. SP7 should fix the class of volatility failures, not only the one observed crash.

The project direction from ADR-062 is attributed decision support, not revived in-house return prediction. SP7 must therefore harden weekly jobs without making `run-tournament` seem investable again.

## Goals

- Make `weekly-brief` robust to numpy scalar returns from live/data-provider paths.
- Make the dead `run-tournament` path fail loud instead of publishing an empty success.
- Define a weekly corroboration cadence contract so SP1/SP5 can plug in cleanly later.
- Preserve all `RESEARCH_ONLY`, attributed-not-predicted guardrails.
- Keep the implementation small, test-first, and isolated from SP2-SP6 feature work.

## Non-Goals

- Do not revive, retrain, or improve the legacy prediction ensemble.
- Do not add buy/sell language.
- Do not implement SP2 candidate surfacing, SP3 screener blending, SP4 portfolio verdicts, SP5 forward validation, or SP6 dashboard tabs.
- Do not schedule `resolve-corroboration` until SP5 defines and implements that command.

## Approach Options

### Option A — Minimal Patch

Fix only `HoldingsRiskAssessmentUseCase._vol()` and add one regression test.

Pros: fastest path.
Cons: leaves the same volatility bug in `discipline_backtest.py`; leaves `run-tournament` misleading; does not prepare weekly cadence for corroboration.

### Option B — Reliability Gate (Recommended)

Fix the volatility class, make `run-tournament` fail loud, and document the weekly corroboration cadence contract.

Pros: small scope, directly unblocks later SP4/SP5 work, removes misleading success states.
Cons: less visually exciting than SP6 and does not deliver new user-facing corroboration screens yet.

### Option C — Full Weekly Orchestration

Fix the bugs and build a complete weekly orchestration command that runs `weekly-brief`, `corroborate`, and future resolution steps.

Pros: cleanest future operator experience.
Cons: premature before SP5 exists; risks designing around missing commands and unstable contracts.

Choose Option B.

## Design

### 1. Volatility Reliability

Create `application/volatility.py` with a small pure helper for population standard deviation over recent returns. The helper should:

- coerce each return to a builtin `float`;
- return `0.0` for fewer than two observations;
- produce the same result for Python floats and numpy scalar floats;
- avoid importing numpy into domain or application code only to compute a standard deviation.

Primary targets:

- `application/holdings_risk.py`
- `application/discipline_backtest.py`

Testing:

- Add a `tests/test_holdings_risk.py` regression using numpy float returns that previously reached `_vol()`.
- Add or extend discipline-backtest coverage for numpy scalar returns.
- Add direct helper-level tests for Python floats, numpy scalar floats, and fewer-than-two observations.

### 2. `run-tournament` Fail-Loud Guard

Treat `run-tournament` as a legacy command. It should not silently publish zero picks when predictors are unfitted.

The use case should raise a specific application error before scoring if the configured predictors are not trained/loaded. The CLI should catch that error and exit non-zero with a clear message:

```text
run-tournament is unavailable: no trained model is loaded. This command is a no-op under ADR-062; use corroborate / weekly-brief instead.
```

The guard should fire before any saved recommendation or weekly report is written.

Testing:

- Unit test `WeeklyTournamentUseCase.execute()` with unfitted/fake predictors and assert the specific error.
- CLI test `python -m application.cli run-tournament` path via `CliRunner` exits non-zero and prints the no-op message.
- Store fake asserts no recommendations or reports are saved on failure.

### 3. Weekly Corroboration Cadence Contract

SP7 should define the corroboration cadence and make the existing SP1 command runnable from a normal project install:

- `corroborate` is the weekly evidence-harvest step from SP1.
- `resolve-corroboration` is reserved for SP5 and must not be referenced as an implemented command until SP5 creates it.
- No scheduler config exists in this repo today, so SP7 documents the intended weekly order rather than inventing an OS-level scheduler.
- The documented order should be:

```text
weekly-brief -> corroborate -> resolve-corroboration (SP5 only, once available)
```

The missing SP5 step must be labelled as future/disabled. SP7 must not create a command that pretends resolution exists.

Because `corroborate` is now part of the documented weekly cadence, SP7 should add `ddgs` to the tracked dependency set and lockfile. The live path already depends on it; leaving it only in a local `.venv` would make the cadence unreliable for a fresh install.

### 4. Verification Discipline

SP7 is reliability work, so success requires evidence rather than screenshots:

- targeted volatility tests pass;
- targeted `run-tournament` fail-loud tests pass;
- `weekly-brief` targeted CLI tests pass;
- `corroborate` import/CLI smoke still loads without live network in unit tests;
- dependency metadata includes the `ddgs` runtime package used by `corroborate`;
- no tests make real network calls.

Full `make check` may still depend on the separate `fix/test-hang-timeout` branch. If that branch is not merged into the SP7 worktree, the implementation plan must state the exact targeted verification used and why full-suite verification is deferred.

## Data And Interfaces

No persisted schema changes are required for fixes 1 and 2.

The cadence contract should reuse existing paths:

- `weekly-brief` writes under `data/personal/`.
- `corroborate` persists to `data/recommendations.db` through `CorroborationStore`.
- SP5 will later define forward-resolution samples and `source_reliability` updates.

## Error Handling

- Volatility helper returns `0.0` for insufficient observations; it should not swallow invalid non-numeric data silently.
- `run-tournament` fail-loud errors should be user-readable at CLI level and testable as typed exceptions below the CLI.
- Corroboration cadence docs must distinguish "not implemented yet" from "ran and found nothing."

## Acceptance Criteria

- `weekly-brief` no longer crashes when returns are numpy scalar floats.
- Both `holdings_risk` and `discipline_backtest` are protected from the same stdlib/numpy scalar issue.
- `run-tournament` exits non-zero with a clear no-trained-model/no-op message when predictors are unfitted.
- A failed `run-tournament` writes no recommendations and no weekly report.
- The documented build order is SP7 -> SP2 -> SP3 -> SP4 -> SP5 -> SP6.
- The spec and status docs make clear that SP5 owns `resolve-corroboration`.
- `ddgs` is tracked as a runtime dependency rather than relying on a manually installed local package.

## Implementation Notes For The Plan

- Work in an isolated worktree off `feat/corroboration-engine`; the main tree may be on `fix/test-hang-timeout`.
- Use the uv-managed `.venv`; do not use `pip` directly.
- Start with failing tests for the numpy scalar volatility bug and the fail-loud tournament behavior.
- Keep scheduler changes documentation-only until SP5 creates `resolve-corroboration`.
- Do not let implementer subagents run git; the controller owns commits and branch state.
