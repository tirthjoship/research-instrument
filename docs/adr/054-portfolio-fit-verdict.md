# ADR-054: Portfolio-Fit Verdict — Evidence + Fit Without Prediction

**Date:** 2026-06-11
**Status:** Accepted
**Deciders:** Tirth Joshi
**Builds on:** ADR-052 (CRO direction; alpha hunt closed — recommender ABSTAINS),
ADR-046 (momentum exits falsified), ADR-053 (Unit B practical KILL), the dashboard
realignment (7-tab honest cockpit, PR #39)

## Context

The Stock Analysis tab answers "tell me about this stock," but the user's real
question for a family portfolio is "should I get into it?" Seven falsified
hypotheses (ADR-039/043/044/046/049/050/053) mean the project cannot answer that
with a return prediction — and must never imply one (RESEARCH_ONLY, ADR-052).

The question is still answerable WITHOUT prediction. Two things the project CAN
compute with precision:

1. **Evidence quality** — where the stock sits on the existing factual screen
   composite (valuation · quality · health), as a percentile rank of the screened
   universe.
2. **Fit** — what adding the name would do to *this book's* risk shape, using the
   existing Unit A macro-beta machinery and simple position arithmetic.

Neither is a forecast. Both are descriptive.

## Decision

Add a **portfolio-fit verdict** to the Stock Analysis tab: an evidence grade
(STRONG/MODERATE/WEAK/UNKNOWN) plus fit flags (BETA_AMPLIFY, CONCENTRATION,
TREND_STATE, DATA_GAP), with plain-English messages. Implemented as:

- `domain/fit.py` — pure verdict logic (stdlib only), with a hard **vocabulary
  invariant**: the output may never contain buy/sell/winner/conviction/predict/
  alpha/outperform. This is enforced by a Hypothesis property test, not a
  convention — drift fails CI.
- `application/fit_use_case.py` — gathers inputs from EXISTING artifacts (latest
  `screen_<date>.json`, `brief_summary.json` macro block, holdings CSV) and an
  injected single-ticker beta function. No new ports, no new adapters.
- Stock Analysis tab — renders one card under the RESEARCH ONLY banner, memoized in
  session_state so the live beta fetch runs once per analyzed ticker, not per rerun.

Design constraints honored:
- **No prediction.** Evidence grade is a rank of present facts; fit is arithmetic on
  current holdings. The card caption states the tool does not forecast returns.
- **Reuse over rebuild.** Composite rank is derived from the screen's own
  distribution; beta reuses `MacroBetaUseCase`; the systematic-share threshold is
  read from `config/markets/us.yaml`, never re-declared.
- **Fail-loud, never silent.** Every missing input becomes a labeled DATA_GAP flag;
  no fabricated values.

### Scope deferred (recorded, not built)

- **Sector concentration:** holdings carry no sector field anywhere in the pipeline;
  fetching one per holding would violate the no-new-IO boundary. CONCENTRATION uses
  single-name market-value weight instead. (Also fixed a latent bug found here:
  `top_concentration` had been computed from per-share price, not market value.)
- **Correlation-vs-book fit input:** parked in `docs/HYPOTHESIS_BACKLOG.md` —
  descriptive, medium cost, post-wrap feature work.

## Consequences

- The family gets a one-glance "is the evidence strong, and does this fit our book"
  read without any implied buy/sell call.
- The honesty boundary is now machine-enforced (vocabulary invariant), so future
  edits to the card cannot silently reintroduce prediction language.
- No domain prediction code, no new external dependency, no new port. The project
  stays in its deterministic, fail-loud, passive-accrual wrap state.
