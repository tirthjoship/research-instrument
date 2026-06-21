# STATUS — multi-modal-stock-recommender

**As of:** 2026-06-21
**Branch:** `feat/corroboration-engine` (worktree: corroboration-sp7)
**Phase:** SP7 DONE — weekly job reliability fixed; next = SP2 candidate surfacing

## NEXT ACTION (fresh session — start here)

**Brainstorm + full spec SP2 candidate surfacing.**
Brief: `docs/superpowers/specs/2026-06-20-sp2-candidate-surfacing-brief.md`
Skill order: brainstorming → writing-plans → subagent-driven-development.

Documented build order: SP2 → SP3 → SP4 → SP5 → SP6.
PR #73 (SP1 corroboration core) still OPEN → develop, deferred by user.

## SP7 — DONE (4 commits)

| Fix | File | Commit |
|-----|------|--------|
| holdings_risk numpy-float crash | `application/holdings_risk.py:61` | `f9ce829` |
| discipline_backtest same class | `application/discipline_backtest.py:41` | `dfd0be8` |
| run-tournament fail-loud exit(1) | `application/cli/ml_commands.py` | `c0e1ee6` |
| ddgs runtime dep declared | `pyproject.toml` | `e3bb855` |

Gate: 21 targeted tests pass, mypy --strict 228 files clean, ruff clean.

## Worktree / branch layout

- Main tree: `fix/test-hang-timeout` (CI gate fix, not yet merged)
- This worktree: `feat/corroboration-engine` (SP1 + SP7, PR #73 open)
- Other active worktrees: portfolio-tab-redesign, risk-tab-redesign

## Gotchas

- Use `.venv` (uv-managed): prefix commands with `PATH=.venv/bin:$PATH`
- Full `make check` suite HANGS (open flag: `fix/test-hang-timeout`) — verify via targeted pytest + mypy --strict only
- google.generativeai prints FutureWarning (project-wide, non-blocking)
- factor_percentile is None unless `screen_<date>.json` exists (run `screen-candidates` first)
- SP2 depends on SP1 (`CorroboratedCandidate`, `CorroborationStore`) — PR #73 must merge before SP2 ships
