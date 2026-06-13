# ADR-055: Research Instrument Redesign — Honest UI, Not a Framework Migration

**Date:** 2026-06-12
**Status:** Accepted
**Deciders:** Tirth Joshi (with Fable main loop)
**Builds on:** ADR-052 (RESEARCH_ONLY — recommender abstains), ADR-054 (portfolio-fit verdict),
the v2 6-tab dashboard (PR #46/#47), and the **rolled-back cockpit redesign** (PR #50 → reverted
PR #52) whose lesson — *consolidation ≠ redesign; never ship UI the user hasn't seen run* — is
binding here.

## Context

The v2 6-tab dashboard is substance-rich but **presentation-flat and unintuitive**: default
Streamlit look, default Plotly, walls of gray text, no hierarchy, no brand. Worse, the project's
greatest asset — intellectual honesty (falsification, abstention, process-over-prediction) — is
buried, so it reads as "empty/broken" rather than "rigorous." The user benchmarked against
SimplyWall.st ("padding, intuitiveness") and asked whether the fix required migrating to **Plotly
Dash** or a **Next.js** dashboard.

Investigation (three live Streamlit spikes, plus Gemini + ChatGPT triangulation):
- The flatness is **unspent CSS, not a framework ceiling.** A pure-Streamlit spike (header/
  fingerprint stripped, real design system) hit the SWST bar.
- Dash = full rewrite into a callback paradigm for the *same* problem (still flat without a design
  system). The Next.js repo = wrong domain (bank-balance aggregator) and wrong stack.
- The user twice reached for "re-add return predictions" to make the UI feel decisive. This was
  surfaced and rejected: SWST itself does **not** predict returns; its decisiveness comes from
  honest evidence verdicts. The fix is **bolder honest verdicts**, not forecasts.

## Decision

Redesign the dashboard in place as a **"Research Instrument"** — distinctive, intuitive, and
SWST-grade — **staying on Streamlit**. Three strands, all honesty-safe:

1. **Visual design system** (`adapters/visualization/components/styles.py` + a shared Plotly
   template; **extend** existing `charts.py`/`hero.py`/`cards.py`/`metrics.py`/`verdicts.py`, do not
   duplicate): white/cool base with an **owned petrol-teal accent** (deliberately *not* the warm
   cream that read as Anthropic branding), a 3-font pairing (**Fraunces** display serif · **IBM
   Plex Sans** body · **IBM Plex Mono** metrics), generous padding, soft cards, bold-but-scarce
   semantic color (crimson=falsified/broken, amber=abstain/caution, green=pass/intact).
2. **Information architecture / intuitiveness:** a "start-here" hero, de-densified tabs
   (progressive disclosure), **in-app drill-down** (click a ticker → its Stock Analysis) plus an
   external ↗ Yahoo link, and a **comprehensive hover-tooltip glossary** on every term (extend
   `glossary.py` 12 → ~40 entries; one `tooltip()` helper, single source of truth).
3. **Honest confidence:** present the evidence/risk/trend/quality verdicts the engine *already*
   computes — boldly, with score dots and color — instead of whispering them. Plus signature
   legibility elements: **Evidence Ledger** strip, **anti-KPI** proof tiles (Rank-IC 0.004 /
   ~50%=EMH / 512→0 as badges of honor), and the Screener **abstention funnel**.

**No framework migration. No return predictions.** Spec: `docs/superpowers/specs/2026-06-12-
research-instrument-redesign-design.md`.

Design constraints honored:
- **No prediction.** The FORBIDDEN_WORDS invariant (`domain/fit.py`, ADR-054) holds on every new
  component, source and rendered output; snapshot tests added for the honest states.
- **Reuse over rebuild.** Restyle + additive only; no working tab or logic deleted.
- **Show before ship.** Staged rollout — Home built first, launched, screenshotted, approved
  before any merge; then each remaining tab the same way. Nothing merges unseen.

## Scope deferred (recorded, not built)

- **DCF fair-value model (E4):** SWST's "undervalued" signature. Deferred to a later phase, and only
  ever as a *range* (bull/base/bear) with explicit assumptions + sensitivity — never a point target
  (false precision is the cardinal DCF sin). See ADR-056.
- **Framework re-evaluation:** revisit only if a *specific interaction* proves impossible in
  Streamlit 1.58 — none found so far.

## Consequences

- The dashboard becomes a distinctive, intuitive product that makes the project's rigor legible in
  the first ten seconds — addressing visual polish, intuitiveness, and employer-impact at once,
  with zero honesty cost.
- The honesty boundary is reinforced, not weakened: the "predict" pull was caught and the redesign
  routes all decisiveness through attributed/factual verdicts.
- The "show-before-ship" discipline is now an architectural rule for UI work, closing the gap that
  produced the cockpit rollback.
