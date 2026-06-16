# Research — Risk Tab redesign: existing infrastructure (reuse map)

**Date:** 2026-06-15 · **Purpose:** map what already exists so the Risk-tab (v8) spec rebuilds on top, not from scratch.

## High-level summary

The macro-beta "scrubber" backing the Risk tab is fully built and tested: a Ridge factor model
(`RidgeMacroBetaEstimator`), pure-math domain (`domain/macro_beta.py`), an orchestrating use case
(`MacroBetaUseCase`), a risk rubric (`domain/risk_rubric.py`), a serializer (`brief_to_summary_dict`),
and a rendering tab (`tabs/risk.py`) that already draws hero metrics, distance-ramp band strips, a
factor bar, a systematic/idiosyncratic donut, and flag cards. The dashboard also already owns a deep
reuse library: `tooltip()` + central `GLOSSARY`, `apply_dossier_template()`, `render_verdict_card()`,
the v9 `decision_card` family, the full **Gemini "cited case"** stack (adapter → rate-limiter → weekly
cache → template fallback → `render_gemini_read`), the **fail-safe privacy guard** `is_local_runtime()`,
and the `FORBIDDEN_WORDS` honesty invariant. The v8 design therefore needs **mostly new derived
statistics + a UI rewrite of one file**, reusing every cross-cutting concern.

## What EXISTS (reuse directly)

### Domain / computation
- `domain/models.py:448-498` — `MacroFactorBeta`, `HoldingMacroExposure`, `MacroBetaFlag`, `BookMacroExposure` (frozen dataclasses, extensible).
- `domain/macro_beta.py` — `daily_returns` (19-32), `align_returns` (35-51), `book_return_series` (54-74), `net_beta` (77-86), `build_flags` (89-154), `aggregate_macro_exposure` (157-196).
- `adapters/ml/macro_beta_analyzer.py:22-61` — `RidgeMacroBetaEstimator.estimate()` → `(betas, r2)`; de-meaned, alpha scaled by mean feature variance; `_MIN_POINTS=20`.
- `application/macro_beta_use_case.py:48-148` — `MacroBetaUseCase.execute()`: per-holding betas (headline 252d / drift 63d), book-level fit, `systematic_share = book R²`, coverage tracking. Holds per-holding aligned returns (`holding_rets`) in memory.
- `domain/risk_rubric.py` — `NetBetaBand`/`ShareBand` enums, `classify_net_beta`, `classify_systematic_share(flag=0.60)`, `net_beta_position`.
- Config `config/markets/us.yaml:39-52` — factors `[SPY, TLT, UUP, XLE]`, windows 252/63, `ridge_alpha 0.2`, thresholds (systematic 0.60, factor_dominance 0.25, drift 0.50).

### Data contract
- `application/brief_summary.py:55-71` — serializes the `macro` block. **Thin:** emits `net_beta_by_factor`, `systematic_share`, `idiosyncratic_share`, `dominant_factor`, `flags` (kind strings only), `coverage_holdings`, `total_holdings`. **Omits** `coverage_value_frac`, per-holding detail, and everything v8 adds.
- `adapters/visualization/data_loader.py:298-308` — `load_brief_summary()` → dict|None.
- Written by `application/cli.py` `weekly-brief` (~3111-3174) to `data/personal/brief_summary.json` (gitignored).

### UI / components
- `tabs/risk.py:1-362` — current render: header+ADR-052, vitals row, `_render_band_strips` (58-198), factor bar + donut, conclusion, flag cards via `render_verdict_card`, coverage footer. Uses `ri-*` classes.
- `components/styles.py` — `inject_global_css()`; design tokens (Fraunces / IBM Plex Sans / IBM Plex Mono; `--ri-*` colour vars incl. `--ri-teal #0F6E80`, `--ri-amber #C9810E`, `--ri-green #1F9254`, `--ri-crimson`). `ri-sec`, `ri-metric-*`, `ri-conclusion`, `.gai`, decision-card classes.
- `components/tooltip.py:10-16` — `tooltip(term, label)` → `<span class="ri-ttip">…<span class="ri-tip">DEF</span></span>`; definitions from `components/glossary.py` `GLOSSARY` (KeyError if missing — must add new terms).
- `components/metrics.py:42-65` — `render_verdict_card(st, verdict, tone, details)`.
- `components/charts.py:35` — `apply_dossier_template(fig)`; plus `gauge_chart`, `comparison_bars`, `grade_donut`, `ownership_pie`, `cluster_bubble`, etc.
- `components/decision_card.py` — v9 collapsed/expanded card + `_case_html` (Google-AI block pattern).

### Gemini "second opinion" stack (reuse for the Risk AI panel)
- `adapters/ml/gemini_narrator.py:39-58` — `GeminiNarratorAdapter.summarize_case(CaseContext)→CaseResult`, `gemini-2.0-flash`, forbids FORBIDDEN_WORDS in prompt, fail-safe `data_gap=True`.
- `application/rate_limited_summarizer.py:23-50` — `RateLimitedCaseSummarizer` (5s buffer, `GEMINI_MIN_INTERVAL_S`).
- `application/case_cache.py` — `write_case_cache`/`load_cached_case`, `data/personal/cited_cases.json`.
- `application/case_builder.py:22-46` — `TemplateCaseSummarizer` (deterministic fallback, no network).
- `application/card_loading.py:30-50` — `select_case_summarizer()` (Gemini-if-key else template).
- `adapters/visualization/card_fetch.py:22-48` — `get_case_on_expand()` cache-first pattern.
- `components/gemini_read.py:43-101` — `render_gemini_read(CaseResult)`.
- `domain/case_models.py` — `CasePoint`, `CaseContext`, `CaseResult`.

### Honesty / privacy rails
- `application/runtime_guard.py:32-39` — `is_local_runtime()` (env `STOCKREC_LOCAL_ONLY=1` + loopback server + loopback client, fail-safe False). CI tripwire `tests/application/test_runtime_guard.py`.
- `domain/fit.py:13-21` — `FORBIDDEN_WORDS` (`buy/sell/winner/conviction/predict/alpha/outperform`); `label="RESEARCH_ONLY"`. Scanned by ~17 test files.

### Tests (extend, don't break)
- `tests/test_macro_beta.py` (+ Hypothesis property tests), `tests/test_macro_beta_analyzer.py`, `tests/test_macro_beta_use_case.py`, `tests/test_risk_tab.py` (additivity: pre-existing elements still render).

## What does NOT exist yet (v8 must add)

**Derived statistics (new domain math, all descriptive — no prediction):**
1. **Effective Number of Bets (ENB)** — PCA of the holdings return covariance → eigen variance shares → `exp(−Σ pᵢ ln pᵢ)`; plus PC-1/2/3 variance shares + loadings. *Needs the holdings covariance matrix, which the use case can build from `holding_rets` but does not currently persist.*
2. **Bootstrap CI** for systematic share + **adjusted R²**.
3. **Per-factor beta confidence intervals** (analytic or bootstrap) → suppress factors whose CI straddles 0.
4. **Downside (semi) beta** — beta on market-down days only.
5. **Risk contribution per holding** (Euler / marginal contribution to variance, sums to 100%).
6. **VIF** per factor (collinearity caveat).
7. **Diversification ratio** (Σ wᵢσᵢ / σ_portfolio).
8. **Sector concentration** — GICS sector per holding + HHI. *No sector source today — needs a sector provider/cache (yfinance `.info` sector) + descriptive "gaps" list.*
9. **Drift history** — 8-week systematic-share series for the sparkline. *No weekly history persisted today.*

**Data contract:** extend `BookMacroExposure` + `brief_to_summary_dict` to serialize all of the above (incl. per-holding risk contribution + sector). Bump the JSON `macro` schema.

**UI:** full rewrite of `tabs/risk.py` render to the v8 status-first design (status banner, vitals incl. ENB/downside/CI, dials, evidence bands w/ bootstrap band, factor chart w/ whiskers+suppression, ENB section + drill-down, sector breakdown + descriptive gaps, who-owns=risk-contribution, drift sparkline, Google-AI second-opinion panel, teach-me, flags, tooltips). New status-first CSS tokens + many new `GLOSSARY` entries.

**Risk AI panel:** new "risk blind-spot" summarizer call (reuse Gemini stack + cache + `is_local_runtime` gate + RESEARCH_ONLY), distinct from the per-stock cited case.

## Key constraints carried from ADR-052 / memory
- Dials are **heuristic surfacing, not validated edges**; risk = **character not quality** (no good/bad grade on magnitude).
- **Attributed-not-predicted**: sector "gaps" are descriptive only (never "buy X"); Google AI is an attributed second opinion, never the verdict.
- Colour spine (v8): green = within-line · grey = neutral character · amber = line-crossed · petrol = data.
- Mockup of record: `.superpowers/brainstorm/65055-1781542394/content/risk-v7.html` (eyebrow "v8 — full methodology").
