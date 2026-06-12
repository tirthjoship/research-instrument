# STATUS — multi-modal-stock-recommender

**As of:** 2026-06-12
**Branch:** feat/cockpit-redesign
**Phase:** Cockpit redesign — IMPLEMENTED + green, pending verification sweep then PR to dev

## Current State

Two-surface dashboard shipped on `feat/cockpit-redesign`. `make check` green:
**1613 tests passing, 94% coverage, mypy strict clean.**

**What was built:**
- `adapters/visualization/cockpit/` package — assembler + 5 section renderers in
  priority order: danger strip → your calls → week retro → look-into-next → lookup
  (with stock-detail `st.dialog` drawer).
- `rank_by_diversification` — diversification-first candidate framing in look-into-next.
- Universe guard (Task 0): stale tickers pruned before build.

**What was deleted:** 4 v2 tab renderers (home/screener/risk/my_portfolio) + their tests.

**What was relocated:** stock_analysis → cockpit lookup/drawer; trust → Showcase surface.

**Two surfaces:**
- **Cockpit** — single-scroll operational view (danger → calls → retro → look-into-next
  → lookup). One design system. RESEARCH_ONLY + FORBIDDEN_WORDS invariants hold.
- **Showcase** — methodology/falsification Trust content, intact and reachable.

## Next Action

1. **Opus verification sweep** (conformance, honesty-drift, integration) — run before PR.
2. `git push -u origin feat/cockpit-redesign` + open PR to `dev`.
3. CI green → merge feature → dev → main per project flow.

## Queued (separate specs, NOT now)

- **A2 — Showcase surface** (recruiter falsification/methodology narrative). Trust content
  stays reachable as-is until then.
- **Project B — Alpha re-open.** User wants falsification gates kept OPEN to keep testing
  (news/sentiment → next-week, cross-stock lead-lag). MUST go through pre-registration —
  NOT a re-run of the falsified ADR-044 divergence thesis (that's p-hacking). Needs a
  genuinely new hypothesis or a named flaw in ADR-044, pre-registered. Run
  `ds-methodology-review` first.

## Caveats

- RESEARCH_ONLY + FORBIDDEN_WORDS invariant holds on every cockpit surface.
- `data/reports/screen_20*.json` gitignored — run `git checkout data/reports/` before
  pre-commit if those files appear as untracked changes.
- Standing watch: ADR-048/051 discipline forward-calibration gate resolves ~mid-July 2026.
