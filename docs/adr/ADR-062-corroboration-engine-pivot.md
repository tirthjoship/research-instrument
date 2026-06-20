# ADR-062: Pivot to a Corroboration Engine (attributed, not predicted)

**Status:** Accepted
**Date:** 2026-06-20
**Supersedes direction of:** the dead `run-tournament` ML prediction path
**Related:** ADR-045 (prediction→discipline pivot), ADR-048/051 (forward-gate pattern), ADR-049
(RESEARCH_ONLY screen gate); research `research/2026-06-20-prediction-and-surfacing-state.md`

## Context

Eight pre-registered alpha/prediction hypotheses have now been run; **every one failed an honest
out-of-sample bar** (1 NULL, 3 KILL, 3 INCONCLUSIVE, 1 RESEARCH_ONLY — full table in the research doc).
Several "passing-looking" results were falsified only after Opus fixed gate-math / transaction-cost bugs
that had made them look better — so the nulls are conservative. The one hypothesis with a structural
edge argument (sub-$1B insider clusters, ADR-053) showed gross signal but dies on costs and needs paid
survivorship-complete data.

Separately, the live `run-tournament` ML path is structurally dead: training never persists, serving
never loads → 0 picks every run (silent). The investable universe is frozen to static lists, so no new
ideas can enter. The user wanted (a) a weekly review of holdings with a forward direction, and (b)
surfacing of new candidates from credible public sources.

## Decision

Build a **Corroboration Engine** (sub-project 1 of 5) and treat it as the project's core going forward:

1. **Attribute, do not predict.** Harvest what credible *free* sources recommend, show it as *theirs*
   with a verified citation, and stress-test each name against our existing signals (factor screen,
   trend health, divergence, discipline). Output a `CorroboratedCandidate` + theme/sector
   `DirectionalView`. `convergence` is an evidence-strength label, **never** a return forecast.
2. **Decouple search from LLM.** A free search API (Tavily→Brave→DDG) provides *real* citable URLs; an
   LLM (Gemini→Groq, via a self-updating `ModelRegistry`) only summarizes the text behind a verified
   URL. The LLM never sources a citation — this removes the hallucinated-citation risk.
3. **Validate forward-only.** Harvested recommendations cannot be backtested (no historical snapshot).
   Predictive validity is deferred to a pre-registered, forward-accruing Hypothesis #9 gate (sub-project
   5), mirroring ADR-048. RESEARCH_ONLY until/unless that gate passes. A limited, *labelled* historical
   sanity check is permitted on dated sources only (analyst events, dated news) — sanity, not verdict.
4. **Honest "self-improvement."** Reuse the `source_reliability` table; reweight sources by *proven*
   weekly forward hit-rate. The `ModelRegistry` auto-discovers free models (drops deprecated, adds new) —
   availability, not quality. Neither claims more than it can prove.

## Consequences

- One core feeds four consumers (surfacing SP2, screener SP3, portfolio-verdict SP4) + the SP5 gate, plus
  a dashboard surface (SP6). Weekly-job reliability (SP7) is fixed first.
- We stop spending effort reviving in-house return prediction; any revival must earn it through #9.
- Free-tier only; no single-vendor lock-in; no scraping that violates ToS (scraping is best-effort/free).
- Risk: corroboration may itself prove to have no forward edge (#9 could be the 9th null). That is an
  acceptable, honest outcome — the engine is still a useful attributed decision-support instrument with
  no predictive claim, and #9 settles the alpha question without self-deception.

## Spec/plan artifacts

- Spec: `docs/superpowers/specs/2026-06-20-corroboration-engine-design.md`
- Plan: `docs/superpowers/plans/2026-06-20-corroboration-engine.md`
- Forward briefs: `docs/superpowers/specs/2026-06-20-sp2..sp7-*.md`
