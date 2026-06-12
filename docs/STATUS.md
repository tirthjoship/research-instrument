# STATUS — multi-modal-stock-recommender

**As of:** 2026-06-12 (evening)
**Branch:** feat/cockpit-redesign (cockpit spec committed; NOT implemented)
**Phase:** Cockpit redesign — brainstormed, spec written, awaiting validation

## Current State

Dashboard v2 SHIPPED earlier today (PRs #46–#49, develop ≡ main, suite 1628). Then a
brainstorm (`/brainstorming` + `/grill-me`, 6 screenshots reviewed) re-opened the project
from maintenance: the v2 dashboard is six incoherent mini-apps, and the tool is all
defense — it never tells the user what to research next.

**Decisions locked (see the spec):**
- Two audiences → **two surfaces**: a fast family **cockpit** (build now) and a deferred
  recruiter **showcase** (A2). They must not share pixels.
- **Greenfield the cockpit** on top of an UNTOUCHED hexagonal core (domain/ + application/
  stay). Single-scroll, strict priority order: danger → your-calls(+log) → look-into-next →
  lookup. Stock detail = a drawer. One design system (kills the 4-visual-languages problem).
- **Honest discovery** ("look into next"): split factual rank (always shown) from the
  tradeable-edge verdict (stays abstaining, shown inline). **Diversification-first** framing.
  Prereq: clean the stale screen universe.
- Kill legacy cruft in the drawer (39.3 score, divergence tables, Sundial default).

**Spec:** `docs/superpowers/specs/2026-06-12-cockpit-redesign-design.md` (DRAFT — has 4
open questions for validation).

## Next Action (next session)

1. **Validate the cockpit spec** (read it; resolve the 4 open questions — esp. whether the
   confirm-and-log write belongs in the cockpit or stays CLI-only).
2. If it holds → `superpowers:writing-plans` → implement via subagent-driven-development
   (Sonnet impl, Opus review), feature branch → develop → main (keep in sync).
3. Design is provisional — "investigate if it holds when we validate the spec" (user).

## Queued (separate specs, NOT now)

- **A2 — Showcase surface** (recruiter falsification/methodology narrative). Trust content
  stays reachable as-is until then.
- **Project B — Alpha re-open.** User wants the falsification gates kept OPEN to keep testing
  (news/sentiment → next-week, cross-stock lead-lag). MUST go through pre-registration — NOT
  a re-run of the falsified ADR-044 divergence thesis (that's p-hacking). Needs a genuinely
  new hypothesis or a named flaw in ADR-044, pre-registered. Run `ds-methodology-review` first.

## Caveats

- All real screens abstain (0 candidates) + stale universe → discovery is dead today; the
  cockpit's factual-rank top-N is designed to surface anyway. Clean the universe first.
- `data/reports/screen_20*.json` gitignored; `git checkout data/reports/` before pre-commit.
- RESEARCH_ONLY + FORBIDDEN_WORDS invariant holds on every new cockpit surface.
- Standing watch: ADR-048/051 discipline gate resolves ~mid-July 2026.
