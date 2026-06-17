# ADR-061: Workflow + token-efficiency initiative (bottlenecks to target in a dedicated session)

**Date:** 2026-06-17
**Status:** Accepted (direction); **work deferred to a dedicated fresh session**
**Deciders:** Tirth Joshi

## Context

The test suite is at **~2145 tests / 225 files (~35k test LOC) and climbing**. `make check` runs
`lint + typecheck + test-cov`, where `test-cov` is `pytest tests/ -v --cov=… --cov-fail-under=90` —
**serial, verbose, with coverage on every invocation** (~40-45s wall-clock). During the Risk-tab work the
full gate was re-run after nearly every micro-edit, which is slow and token-heavy (each run's output +
coverage table is read back). Tirth flagged this as inefficiency worth a dedicated pass.

Beyond tests, this session surfaced other token/efficiency bottlenecks:
- **Oversized modules** inflate every read/edit: `application/cli.py` **3440 LOC**, `adapters/visualization/tabs/risk.py`
  **1710**, `adapters/visualization/components/styles.py` **1505**, `stock_analyzer.py` 1305,
  `research_candidates.py` 1211, `sqlite_store.py` 1093. Touching any of these costs disproportionate tokens.
- **Live-screenshot verification** (CDP full-page PNGs) is correct but very token-expensive to read back.
- **mypy cache flakiness**: `make typecheck` (191-file view) vs the pre-commit hook (196-file view) disagree on
  `google.generativeai` attr-defined — handled via a `disable_error_code` override, but the disagreement wastes cycles.

## Decision

Run a **dedicated efficiency/token-bottleneck session** rather than bolting it onto feature work. Keep `make check`
as the authoritative gate, but make it cheaper to run and run it less wastefully. Candidate work (measure first,
then fix the highest-leverage items):

1. **Parallelise tests** — add `pytest-xdist`; `-n auto` on 8 cores should cut the suite ~4-5× (~40s → ~10s).
   Add a `make test-fast` (parallel, `-q`, no-coverage) for iteration; keep coverage on the gate only. Drop `-v`.
2. **Run discipline (no code, free win):** targeted `pytest <file>` while iterating; full `make check` only at
   checkpoints / before commit — not after every edit. (This session violated that.)
3. **Decompose oversized modules** — split `cli.py` (3440), `risk.py` (1710), `styles.py` (1505) into cohesive
   submodules so reads/edits touch less. Behaviour-preserving; gate-guarded.
4. **Cheaper verification** — prefer targeted element/cropped or lower-res captures, or assertion-based DOM checks
   (the CDP harness can `Runtime.evaluate` instead of returning full-page PNGs) over full-page screenshot reads.
5. **Test-value review** — prune redundant/low-signal example tests; lean on Hypothesis property tests (per
   CLAUDE.md) where they replace many cases; confirm the 90% coverage gate is meaningful, not padding.
6. **Resolve the mypy env disagreement** at the root if cheap (stub/typed shim) to drop the override + cache churn.

**Baseline before changing anything:** record current `make check` wall-clock + a rough token cost per gate run,
so the wins are measured, not assumed.

## Consequences

- Faster gate + lower per-session token burn; iteration stops paying for the full suite every edit.
- Module decomposition is the riskier item (broad diffs) — do it behaviour-preserving, one module at a time,
  gate-green at each step. Not started here.
- No code changed in this ADR — it records the direction + the measured bottlenecks for the fresh session.

## Related

- `Makefile` (`test-cov`, `check`), `pyproject.toml` (mypy overrides), `project-risk-tab-fix-sprint` memory,
  `reference-streamlit-screenshot-lazy-tabs` (verification cost).
