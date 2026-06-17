# ADR-060: Expand the macro-beta factor universe via long-short FF/AQR factors — not long-only ETF proxies

**Date:** 2026-06-17
**Status:** Accepted (decision); **build deferred to a dedicated, leakage-aware effort**
**Deciders:** Tirth Joshi
**Builds on:** Risk-tab v8 (ADR-052), the R03 fix-sprint item, CLAUDE.md non-negotiable #2 (no look-ahead bias)

## Context

The Risk-tab factor chart ("What's driving it") currently fits **4 factors** — `config/markets/us.yaml`
`macro_beta.factors: [SPY, TLT, UUP, XLE]` (market / rates / dollar / energy). Tirth wants more factors to
better characterize what drives the book ("4 is too little to know"). The v8 mockup illustrated 9.

An external review (Cursor) proposed expanding to 9 by adding **long-only ETF proxies** (MTUM, IWF, HYG, IWM,
IWD). This ADR records why that approach is rejected and what the correct expansion is.

### Why long-only ETF proxies are rejected

IWF (growth), MTUM (momentum), IWM (size), IWD (value) are all ~80% correlated with SPY — they are long the
market plus a tilt. Regressing the book on SPY + these overlapping long-only ETFs is severe multicollinearity:
betas become unstable and uninterpretable, bootstrap whiskers blow out, and the VIF>5 callout fires on
*everything by construction*. The user would "see 9 factors" where half the numbers are noise — **less**
signal, not more. (Web-checked 2026-06-17 against factor-construction literature; consistent with the
"mix vs integrate" practice of using standardized, dollar-neutral long-short factors.)

## Decision

**1. The authentic expansion is long-short factor returns** — Fama-French / AQR style: `Mkt-RF, SMB (size),
HML (value), MOM (momentum)`, optionally `RMW (profitability), CMA (investment)`. These are market-neutral by
construction → interpretable, orthogonalized betas — the academic-standard risk decomposition. This is the
only version that actually answers "what drives the book."

**2. It is a dedicated build, not a config edit.** Required:
   - New **data adapter** for Ken French / AQR daily factor returns (Dartmouth CSV or `pandas_datareader` — a
     new dependency; the scrubber `risk_stats_analyzer` is already source-agnostic and consumes a
     `factor_returns` dict, so the analysis layer needs no change).
   - **Point-in-time / leakage handling** — Ken French factors publish with a lag; every factor return used at
     `as_of` must have been published on/before `as_of`. This is CLAUDE.md non-negotiable #2; getting it wrong
     makes backtests lie. This is the bulk of the work and why it is NOT bolted onto a UI fix sprint.
   - Config schema update (factor names, not tickers), `weekly-brief` re-run to populate betas/CIs/VIFs,
     real-beta eyeball, and a methodology review before adoption.
   - Factor display-name map extension (`_FACTOR_DISPLAY_NAMES`) + the VIF cluster callout will then fire
     honestly when genuine correlation exists.

**3. Until built, the Risk tab renders the honest 4-factor count** — never a hardcoded 9, never collinear
proxies. The R03 UI work (DOMINANT badge, READ line, subtitles, dormant VIF callout) already shipped on the 4.

## Consequences

- Honesty preserved: we don't paint 9 bars that lie. The tab shows what the config genuinely fits.
- The expansion is documented, not silently deferred — this ADR is the spec for the next focused effort.
- Re-entry: a dedicated session — methodology review (`ds-methodology-review`) → ADR for the chosen factor
  set + data source + PIT scheme → build (data adapter, config, weekly-brief) → real-beta eyeball.

## Related

- ADR-052 (Risk-tab v8 honesty rails), `project-risk-tab-fix-sprint` memory, `config/markets/us.yaml`.
