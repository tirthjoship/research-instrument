# HANDOFF — Risk Tab redesign build (subagent-driven)

**For:** a fresh Claude Code session that will implement the Risk tab redesign.
**From:** the design/planning session (2026-06-15). That session stays open as the **validation reference**.

## Your job
Execute the implementation plan **task-by-task** using the **`superpowers:subagent-driven-development`** skill
(fresh subagent per task, two-stage review between tasks). Do NOT free-build — follow the plan.

## Read first (in order)
1. `docs/superpowers/plans/2026-06-15-risk-tab-redesign.md` — the plan you execute (14 tasks, TDD, exact code).
2. `docs/superpowers/specs/2026-06-15-risk-tab-redesign-design.md` — the locked design + honesty rails.
3. `research/2026-06-15-risk-tab-existing-infra.md` — what already exists to reuse (don't rebuild).
4. Mockup of record (visual truth): `.superpowers/brainstorm/65055-1781542394/content/risk-v7.html`
   (eyebrow says "v8"). Plan Task 0 freezes a copy to `docs/superpowers/mockups/risk-v8.html`.

## Start with Task 0 — the worktree (isolation is mandatory)
```bash
cd "/Users/tirthjoshi/My Data Science Projects/ML_Portfolio_Projects/multi-modal-stock-recommender"
git worktree add -b feat/risk-tab-redesign ../risk-tab-redesign feat/dashboard-legibility-redesign
cd ../risk-tab-redesign
```
Branch off the **committed** `feat/dashboard-legibility-redesign` HEAD — this avoids dragging in the parallel
Home/Screener sessions' uncommitted edits. Then copy spec/plan/research/mockup into the worktree (Task 0 Step 2)
and confirm `make check` is green before writing code.

## Model strategy (per global CLAUDE.md)
- **Sonnet** for implementation subagents (each task is scoped + spec'd).
- **Opus** for verification between tasks (`superpowers:verification-before-completion` / code review).
- Main loop stays on the user's selected model.

## Non-negotiable rails (the whole point of this project — verify on EVERY task)
- Dials are **heuristic surfacing, not validated edges** (ADR-052). Risk = **character, not quality** — never grade
  magnitude good/bad. Distance spectrums symmetric.
- **Attributed-not-predicted:** sector gaps are descriptive only, tagged `NOT A BUY CALL`. Google AI = attributed
  second opinion, `RESEARCH_ONLY`, never the verdict, gated by `is_local_runtime()` (fail-safe hidden off-local).
- No `FORBIDDEN_WORDS` (`buy/sell/winner/conviction/predict/alpha/outperform`) in any rendered string — tests scan.
- ENB "named bets": derive from real PC loadings; if inconclusive → generic "Bet N" + DATA-GAP, **never invent a
  story**. Render only the factors the config fits (currently 4 in `us.yaml`) — do NOT hardcode the mockup's 9.
- Mockup numbers (1.18×, 71%, ENB 3.2, NVDA 14%) are **illustrative placeholders**, not committed values.

## Gate before declaring done
`make check` (ruff + mypy --strict + pytest ≥90%) green · FORBIDDEN_WORDS + privacy tripwire pass · honesty footer
present · live-app eyeball of the Risk tab against `docs/superpowers/mockups/risk-v8.html`
(`STOCKREC_LOCAL_ONLY=1 streamlit run adapters/visualization/dashboard.py`). Then `superpowers:requesting-code-review`
(Opus) and `superpowers:finishing-a-development-branch` (PR to `develop`, stacks on PR #58 per ADR-052 memory).
Before any main merge: confirm no surface presents risk character as a good/bad grade.

## When done
Land the branch and tell the user. The **design session stays open** to validate the built tab against the locked
mockup + spec, section-by-section (status banner, vitals incl. ENB/downside/CI, dials, bootstrap band, factor
whiskers + ≈0, ENB drill naming the bets, sector gaps, who-owns risk%≠$, drift, Google-AI panel, tooltips).
