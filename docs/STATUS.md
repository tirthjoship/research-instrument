# STATUS — multi-modal-stock-recommender

**As of:** 2026-06-20 (session 3)
**Branch:** `feat/corroboration-engine` (off `develop`)
**Phase:** Corroboration Engine (ADR-062) — spec + plan DONE, ready to implement SP1

## NEXT ACTION (fresh session — start here)

**Implement SP1** from the plan (11 TDD tasks, Sonnet subagents recommended):
```
docs/superpowers/plans/2026-06-20-corroboration-engine.md
```
Tasks 1–4, 8 run on fakes, no API keys. Tasks 5/7 need free Tavily + Gemini keys in `.env` for live
smoke (build/test core offline first, wire live last). Gate per task with `make test-tab`/targeted
pytest; full `PATH=.venv/bin:$PATH make check` at the end (Task 11).

**Use `.venv`, not miniforge** — `make` targets need `.venv/bin` on PATH (xdist 3.8.0 lives there).

## What this engine is (ADR-062)
Harvest credible free-source recommendations → verify citations → stress-test vs existing signals →
emit `CorroboratedCandidate` + `DirectionalView`. **Attributed, RESEARCH_ONLY, NOT a forecast.** 8 prior
alpha hypotheses all failed (see `research/2026-06-20-prediction-and-surfacing-state.md`). Prediction
claim deferred to forward-only Hypothesis #9 (SP5). Decoupled Search(Tavily→Brave→DDG)+LLM(Gemini→Groq
via ModelRegistry); LLM never sources a citation.

## Roadmap (sub-projects — each needs own brainstorm→plan)
| SP | What | Brief |
|----|------|-------|
| 1 | Corroboration core | spec+plan DONE (this branch) |
| 2 | Candidate surfacing | `specs/2026-06-20-sp2-candidate-surfacing-brief.md` |
| 3 | Screener revamp | `specs/2026-06-20-sp3-screener-revamp-brief.md` |
| 4 | Portfolio-verdict integration | `specs/2026-06-20-sp4-portfolio-verdict-brief.md` |
| 5 | Hypothesis #9 forward gate | `specs/2026-06-20-sp5-hypothesis9-forward-gate-brief.md` |
| 6 | Stock-analysis tabs (dashboard) | `specs/2026-06-20-sp6-stock-analysis-tabs-brief.md` |
| 7 | Weekly-job reliability (do first?) | `specs/2026-06-20-sp7-weekly-job-reliability-brief.md` |

## Open branches — NOT PR'd (decide when to merge → develop)
- `feat/questrade-holdings` (`4afd564`) — real Questrade CSV holdings, 10 tests green
- `fix/yfinance-throttle` (`0b4d692`) — throttle+backoff, fixed the 429 sweep; 264 smoke green
- `feat/corroboration-engine` — research + spec + plan + 6 briefs + ADR-062 (docs only so far)

## Known bugs / gotchas
- `weekly-brief` CRASHES: `holdings_risk.py:61` numpy-float → `statistics.pstdev` (Py3.12). Fix = SP7 #1.
- `run-tournament` = dead ML path, silently 0 picks (no model persisted/loaded). SP7 #2 = fail loud.
- `data/reports/*.json` regenerates — always unstaged, never commit.
- Efficiency overhaul (ADR-061) merged to main; STATUS was stale at session start — now corrected.
