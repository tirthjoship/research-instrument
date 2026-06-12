# STATUS — multi-modal-stock-recommender

**As of:** 2026-06-12
**Branch:** feat/cockpit-redesign
**Phase:** Cockpit redesign — SHIPPED & MERGED (develop ≡ main). Between phases.

## Current State

Two-surface cockpit dashboard merged to **develop and main** (PR #50). Decision recorded
in **ADR-055**. `make check` green: **1616 passing, 94% coverage, mypy strict clean.**
Opus verification sweep done — 2 findings fixed (diversification corr date-aligned via
joint dropna; empty-`as_of` write guarded) + 3 regression tests.

Completed specs/plans were **archived** to `docs/superpowers/archive/` (18 specs + 16
plans). Active `specs/`/`plans/` dirs are intentionally empty — no open build for the
current phase. This is the anti-drift reset.

**What was built:**
- `adapters/visualization/cockpit/` package — assembler + 5 section renderers in
  priority order: danger strip → your calls → week retro → look-into-next → lookup
  (with stock-detail `st.dialog` drawer).
- `rank_by_diversification` — diversification-first candidate framing in look-into-next.
- Universe guard (Task 0): stale tickers pruned before build.

**What was deleted:** 4 v2 tab renderers (weekly_brief, research_candidates, positions,
stock_analysis) + their tests. Compute stays in the core.

**What was relocated:** stock_analysis render → cockpit lookup/drawer; `tabs/risk.py` → danger
drill-down (KEPT); `tabs/trust.py` → Showcase surface (KEPT).

**Two surfaces:**
- **Cockpit** — single-scroll operational view (danger → calls → retro → look-into-next
  → lookup). One design system. RESEARCH_ONLY + FORBIDDEN_WORDS invariants hold.
- **Showcase** — methodology/falsification Trust content, intact and reachable.

## Next Action

Pick the next phase and brainstorm it (`superpowers:brainstorming` → `writing-plans`):
- **A2 — Showcase surface** (recruiter falsification/methodology redesign), OR
- **Project B — Alpha re-open** (run `ds-methodology-review` + pre-register FIRST).

No open spec/plan exists yet; start one before touching code.

## Deferred (minor, from Opus sweep — fix in a follow-up, not blocking)

- `discipline_log.append_assessments` is non-atomic: a crash mid-loop half-logs a week and
  the `as_of` idempotency guard then treats it as done. Make the append all-or-nothing.
- `_calls.confirm_and_log` overwrites (does not sum) shares for duplicate-ticker holdings.
- Tighten the `cockpit.stock_detail` mypy override (`warn_return_any=false`) to an inline
  ignore on the one `_ensure_fit_cached` return.
- Dead `cp-row` CSS class hook in `_discover.py` (renders fine via `ws-card`; define or drop).

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
