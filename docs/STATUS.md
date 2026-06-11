# STATUS — multi-modal-stock-recommender

**As of:** 2026-06-11
**Branch:** feat/dashboard-realignment (PR open → develop)
**Phase:** 5 — Dashboard complete; awaiting PR merge

## Current State

Dashboard realignment (13-task plan) fully committed on `feat/dashboard-realignment`.

7-tab honest cockpit:
- Weekly Brief · Research Candidates · Risk · My Portfolio · Stock Analysis · Falsification Lab · Methodology

Deleted: command_center.py, market_pulse.py, model_confidence.py (ADR-044 verdict)

Test suite: **1561 passed, 0 failures** (baseline was 1542).
All pre-commit hooks pass (black, isort, mypy strict, ruff, secrets).

## Next Action

1. Merge PR feat/dashboard-realignment → develop (review open)
2. After merge: start Phase 6 (live calibration gate — ADR-051 readiness tracking)
   - Gate opens ~mid-July 2026 when ≥30 REDUCE flags resolve across ≥3 dates

## Caveats

- `data/personal/` is gitignored (holdings, brief_summary.json, discipline_log.jsonl)
- Saturday job (`scripts/discipline_weekly_review.sh`) regenerates dashboard JSON artifacts
- RESEARCH_ONLY mode: no buy/sell language anywhere in the UI
- All hypotheses tested to date: 4 KILL, 2 INCONCLUSIVE (see Falsification Lab tab)
