# ADR-060: Expand the macro-beta factor universe via long-short FF/AQR factors — not long-only ETF proxies

**Date:** 2026-06-17
**Status:** Accepted — **BUILT 2026-06-17** (9 factors live; see "Build outcome" below)
**Deciders:** Tirth Joshi
**Builds on:** Risk-tab v8 (ADR-052), the R03 fix-sprint item, the project's non-negotiable on no look-ahead bias

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
     `as_of` must have been published on/before `as_of`. This is the project's no-look-ahead non-negotiable; getting it wrong
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

## Build outcome (2026-06-17)

Built on `feat/risk-tab-fixes`. Final factor set: **`[SPY, SMB, HML, MOM, RMW, CMA, TLT, UUP, XLE]`** (9).
- `adapters/data/fama_french_provider.py` — fetches FF5 + Momentum daily (Ken French, `requests`), caches to
  `data/cache/fama_french_daily.json`, returns a synthetic cumulative price-index per factor so it satisfies the
  existing `PriceProvider` contract (`daily_returns` recovers the factor return). Point-in-time: never returns
  dates after `end`. 14 fixture tests (no network).
- `cli.py` routes `SMB/HML/MOM/RMW/CMA` → FF provider, ETF tickers → yfinance, in `_build_weekly_brief`.
- **`history_days` raised to 500** — FF data lags ~6 weeks (publication), so the regression window had to widen
  for the truncated FF series to clear the 252-pt headline requirement. **Consequence: the macro-beta readout is
  now bounded by the FF publication window (~6 weeks stale).** Acceptable for a descriptive risk tool; a known
  tradeoff of authentic FF factors.
- **Live result validated:** SPY β≈1.20 (DOMINANT), RMW −0.35 (SHORT, profitability tilt), TLT −0.14 (SHORT);
  SMB/HML/MOM/CMA/UUP/XLE **suppressed** (CI straddles zero). Max VIF ≈ 2.3 (HML/CMA) — none >5, so the cluster
  callout stays dormant honestly. This is the real decomposition the rejected collinear ETF proxies would have faked.

## Follow-ups (2026-06-17)

- **Done same session:** per-factor hover tooltips (glossary entries for SMB/HML/MOM/RMW/CMA + macro) and an ⓘ
  on the net-beta tile; factor rows now **sorted by |β|** (real drivers first, suppressed ~0 sink — display only,
  fixed universe); a **"beyond the market" tilts line** separating the expected SPY market core from the
  distinctive tilts (so SPY-dominance reads as normal, not as the whole story).
- **Open (user-approved, future measured effort):** expand the FIXED universe further with theory-justified
  factors (credit/HYG, term spread, commodities) — same measured process, NOT dynamic/adaptive selection
  (selecting factors post-hoc by significance = data-dredging; rejected). SPY structurally dominating a
  long-only equity book is expected and correct, not a defect.

## Related

- ADR-052 (Risk-tab v8 honesty rails), `project-risk-tab-fix-sprint` memory, `config/markets/us.yaml`.
