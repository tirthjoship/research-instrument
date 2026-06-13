# STATUS — multi-modal-stock-recommender

**As of:** 2026-06-12 (late session)
**Branch:** develop ≡ main (v2 baseline, **1628 tests green**). Redesign work will land on a NEW
branch `feat/research-instrument-redesign` — not yet created; **no code changed this session.**
**Phase:** Research Instrument Redesign — **design locked, plan being written, implementation
deferred to a fresh session.**

## Current State

Design-only session. Took the flat/unintuitive v2 dashboard from "maintenance" into a scoped
**redesign**. Validated the direction empirically — **three live Streamlit spikes** (warm→white
pivot, bold semantic color, clickable yfinance, comprehensive hover tooltips) — plus **Gemini +
ChatGPT** triangulation and a **`ds-methodology-review`**. Key resolution: the user twice pulled
toward "re-add return predictions"; both caught and rejected — the honest substitute is **bolder
attributed evidence verdicts** (SWST itself doesn't predict returns).

Artifacts produced (all docs; zero code):
- **Spec:** `docs/superpowers/specs/2026-06-12-research-instrument-redesign-design.md` (14 sections,
  self-reviewed, validated against code).
- **ADR-055** — Research Instrument redesign (stay Streamlit; design system + IA + honest verdicts).
- **ADR-056** — Attributed multi-source evidence dossier (Stock Analysis; E1–E3+E5; E4/DCF deferred).
- **CONTEXT.md** + memory updated with the new terms and the attribution-not-prediction principle.

## Next Action

1. **Fresh session, new branch** `feat/research-instrument-redesign`. Execute the staged plan
   (`/writing-plans` output) — **Stage 0 = design system + Home first**, then launch + screenshot +
   user-approve before any merge (show-before-ship; the cockpit never-again rule).
2. Stages 1–4: Screener (abstention funnel) + Risk → My Portfolio + Trust → Stock Analysis
   (dossier E1–E3/E5 + drill-down + tooltips) → hardening (honest-state snapshot tests).
3. Keep `make check` green each stage; extend `glossary.py` 12 → ~40; **extend** existing
   `components/*` (charts.py/hero.py/cards.py/metrics.py/verdicts.py already exist — do NOT duplicate).

## Caveats

- **Honesty is binding:** FORBIDDEN_WORDS (`domain/fit.py`: buy/sell/winner/conviction/predict/alpha/
  outperform) + RESEARCH_ONLY hold on every new surface; third-party data is **attributed**, never
  adopted as the engine's claim. E4/DCF deferred (and only ever as a range+sensitivity).
- Approved visual reference preserved at `docs/design-references/research-instrument-home-spike.md`
  (throwaway prototype, code embedded) — salvage CSS/components during Stage 0, don't ship as-is.
- All screen artifacts still abstain (0 candidates) — abstention funnel must render on empty weeks.
- `git checkout data/reports/` before any pre-commit/CI verify (tests strip trailing newlines).
- Standing watch (unchanged): ADR-048/051 discipline forward gate ~mid-July 2026 (weekly Saturday
  job); ~Dec 2026 behavior-gap review.
