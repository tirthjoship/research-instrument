# ADR-056: Attributed Multi-Source Evidence Dossier — Stock Analysis Without Prediction

**Date:** 2026-06-12
**Status:** Accepted
**Deciders:** Tirth Joshi (with Fable main loop)
**Builds on:** ADR-044 (sentiment-divergence KILLED, rank-IC 0.004), ADR-045 (Process > Prediction,
Tier 1/2/3 honesty list), ADR-052 (RESEARCH_ONLY), ADR-054 (portfolio-fit verdict + FORBIDDEN_WORDS
invariant), ADR-055 (Research Instrument redesign).

## Context

The user found the Stock Analysis "trend" read — a single `trend_health = (price − SMA)/ATR` flag —
**reductive and "biased"**, and asked why the project can't present rich, multi-source analysis like
SimplyWall.st (news, forecasts, analyst views, sentiment, peer/industry comparison), believing the
engine "could do even better."

A `ds-methodology-review` investigation established:
- **SWST does not predict returns either.** Its apparent "direction" is three honest things:
  factual checks vs thresholds/peers, a DCF *valuation* model, and **attributed analyst consensus**.
  So matching SWST is *compatible* with ADR-044/045 — the falsified thing (forecasting returns)
  is the one thing SWST also avoids.
- **~80% of SWST already exists in code** (`adapters/visualization/tabs/stock_analysis.py`):
  Valuation/Growth/Performance/Health/Ownership/Sentiment/Supply-chain sections, a 6-axis evidence
  snowflake, and an analyst-consensus card (recommendation, mean target, count — `yfinance_adapter`).
- The gap is **presentation + a few attributed additions**, not capability — and the data
  (yfinance analyst, GDELT + Google News, sentiment layers) is already ingested and keyless.

The hazard: enriching with "news / forecast / sentiment" is exactly the territory ADR-044 falsified
if the **engine** uses it to predict. The resolution is **attribution**.

## Decision

Reframe Stock Analysis as an **attributed multi-source evidence dossier**. The honesty mechanism is
**attribution**: third-party forecasts are shown as *theirs*, never adopted as the engine's claim.
In scope:

- **E1 — Industry-relative scoring.** Every axis as a percentile **vs GICS sector peers** (sector/
  industry from yfinance `info`; sector ETFs / supply-chain groups already present). Descriptive
  relative facts. Requires a sane peer set — no spurious peers.
- **E2 — Attributed analyst-estimate panel.** Surface the existing `revision` factor (EPS-estimate
  drift) as a trend + **dispersion** (mean/high/low/count/as-of). Labeled "the Street expects…",
  attributed, never adopted.
- **E3 — News / event CONTEXT panel.** Attributed GDELT + Google News themes, labeled "context, not
  signal" (consistent with the existing falsified-sentiment disclaimer at `stock_analysis.py:572`).
- **E5 — Differentiators surfaced:** portfolio-fit verdict (`fit.py`) + a falsification badge — what
  SWST structurally cannot show.

Honesty constraints (binding):
- **No engine forecast.** Factors (`momentum`, `revision`, `quality`, `value`) stay **descriptive
  percentiles** ("ranks 78th pct vs sector"), not predictions. A Tier-2 signal used *predictively*
  must be pre-registered and falsification-tested first (ADR-045) — out of scope here.
- **FORBIDDEN_WORDS invariant holds** (`domain/fit.py`: buy/sell/winner/conviction/predict/alpha/
  outperform) on all new source + rendered output.
- **Attribution + dispersion always.** yfinance analyst data is laggy/scraped — show count, high/low,
  as-of date; never the mean alone.

Where the project **exceeds** SWST (the honest "better"): portfolio-fit awareness, process/behavior-
gap discipline, and falsification transparency — categories SWST does not occupy. *Not* by
out-predicting — honest return prediction is the Tier-3 fantasy ADR-045 rejects, and SWST doesn't
attempt it.

## Scope deferred (recorded, not built)

- **E4 — DCF fair-value range.** SWST's "undervalued" signature and the strongest portfolio
  skill-demonstrator. Deferred; when built, only as bull/base/bear **range + sensitivity table**,
  framed as "a valuation estimate under stated assumptions, not a price prediction." Never a point
  target. No FORBIDDEN_WORDS in source/output.
- **No SimplyWall.st scraping** — no free API; ToS risk. yfinance + the project's own layers are the
  clean sources.

## Consequences

- Stock Analysis answers "what's the full evidence picture?" at SWST depth while staying strictly
  research-only — the "tunnel vision" critique resolved without re-opening prediction.
- Most additions are presentation of data already ingested; minimal new IO, hexagonal boundaries
  intact (pure peer-percentile math in `domain/`, fetch in existing adapters).
- The honesty distinction — *display attributed third-party forecasts ≠ make our own* — is now an
  explicit, documented project principle.
