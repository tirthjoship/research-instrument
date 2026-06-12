# STATUS — multi-modal-stock-recommender

**As of:** 2026-06-12
**Branch:** feat/dashboard-v2 (spec + plan committed, validated, NOT yet implemented)
**Phase:** Dashboard v2 — execution-ready; fresh session implements

## Current State

Shipped this week (all on main, develop = main):
- Phase 6 fit verdict (ADR-054, PR #40) · UX pass all 7 tabs (PR #42) ·
  yfinance MultiIndex fix (PR #44). Suite **1593 passing**.
- Data refreshed 2026-06-11: brief_summary.json (66 holdings, macro 64% SPY),
  screen_2026-06-11.json (512 universe, 0 candidates — abstained).

**Next up: Dashboard v2** (user round-2 feedback + SimplyWallSt bar):
- Spec: `docs/superpowers/specs/2026-06-12-dashboard-v2-design.md`
- Plan: `docs/superpowers/plans/2026-06-12-dashboard-v2.md` (8 tasks,
  Opus-validated 2026-06-12, 5 findings amended — see plan's Validation status)

## Next Action (fresh session)

1. Read this file, then the v2 plan (it is self-contained; code blocks = spec).
2. Execute via `superpowers:subagent-driven-development` — Sonnet implementers
   (low effort), sequential T1→T8; review checkpoints per established workflow.
3. T8 ships: PR → develop → CI green → merge → develop → main release PR (keep
   both branches in sync — standing user instruction).
4. Model routing: Fable = brainstorm/design/course-of-action; Sonnet = implement;
   Opus = independent review/verification (user-confirmed workflow).

## Caveats

- Streamlit dashboard may still be running on :8501 (background) — restart to
  pick up v2 code during T8 live check.
- All current screen artifacts abstain (0 candidates) → live snowflake will not
  render for any ticker; expected (plan T8 note). Factor branch is fixture-tested.
- `data/personal/` gitignored; test runs strip trailing newlines from 2 tracked
  `data/reports/*.json` — `git checkout data/reports/` before pre-commit verify.
- RESEARCH_ONLY + FORBIDDEN_WORDS invariant applies to every new surface.
- Wrap timeline: v2 is sanctioned UX scope (family usability = project purpose);
  post-v2 → close to maintenance. Calendar: mid-July gate read; Dec review.
