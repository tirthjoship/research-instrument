# Research: Prediction Engine + Candidate-Surfacing State (as-is)

**Date:** 2026-06-20
**Query:** What predictor hypotheses has this project tried (user recalls ~7, all wrong)? What ML
prediction infra exists and where is it broken? What external-source candidate-surfacing exists vs.
is absent? Grounding for a brainstorm on a weekly job that (1) reviews holdings + says what to do
next week, and (2) surfaces new candidates from credible public sources and tries to predict winners.

## High-level summary

The project has run **eight** distinct alpha/prediction hypotheses (the user remembered ~7). **Every
one failed an honest out-of-sample bar** — verdicts: 1 NULL, 3 KILL, 3 INCONCLUSIVE (one a practical
KILL), 1 RESEARCH_ONLY. A 9th test (holdings discipline REDUCE flags, ADR-048) is the only live one,
pending ~mid-July 2026. Several failures were caught only after Opus fixed gate-math/transaction-cost
bugs that would have produced *falsely flattering* results — so the nulls are if anything conservative.

The ML ensemble (`run-tournament`) is **structurally dead**: training never persists to disk and
serving never loads a model — three missing links mean every tournament run scores on an unfitted
model, catches `NotFittedError`, and emits 0 picks. Even if wired, Phase 3A already showed the
technical ensemble is a coin flip (47–52% directional accuracy, p>0.14).

Candidate surfacing is **bounded to static lists**: S&P500 + NASDAQ-100 files, a 28-ticker theme
spine, and a ~120-name hardcoded `_KNOWN_TICKERS` set. **No external recommendation harvesting exists**
— no Morningstar, no Google-Search/Google-AI "stocks to invest in," no web scraping, no LLM candidate
discovery. Gemini is used only to *annotate existing holdings*, never to surface new tickers.

## The 8 hypotheses tried (all failed) + 1 pending

| # | Hypothesis | Signal | Horizon | Verdict | Source |
|---|---|---|---|---|---|
| 1 | Technical ML ensemble (Phase 3A) | 45 technical/macro features | 2/5/10d | **NULL** — 47–52% acc, SHAP 32/45 ~zero, p=0.15 | ADR-012, ADR-038 |
| 2 | Sentiment-divergence lift (Phase 3B) | Flan-T5 + keyword buzz/divergence | 2/5/10d | Not closed standalone; killed by convergent #3/#4 | ADR-011/012 |
| 3 | Multi-dim conviction (smart-money+analyst) | SEC 13D/Form-4 + analyst, 8 dims | 21d | **KILL** — OOS edge halved, p=0.063, CI spans 0; 6/8 dims dead | ADR-039, ADR-043 |
| 4 | Intensity-divergence cross-sectional IC | Wikipedia pageview accel vs price | 5/21/63d | **KILL** — 1m IC=0.004, CI spans 0; all ≪0.02 bar | ADR-044 |
| 5 | Momentum + ATR Chandelier trailing-exit | 200d trend + 12-1 mom + Chandelier | monthly | **KILL** — Sharpe-diff CI [−0.79,+0.62]; DD-cut 40% real | ADR-045/046 |
| 6 | 80/20 TSMOM diversifier sleeve | 12-mo TSMOM, 7 ETFs | monthly | **INCONCLUSIVE** — Sharpe CI misses by 0.0011; DD-cut 17%<25% | ADR-050 |
| 7 | Sub-$1B insider-buy clusters | ≥3 Form-4 buys, 30d window | 21d | **INCONCLUSIVE_THIN_COVERAGE → practical KILL** — 24% coverage, free data can't cover delisted micro-caps | ADR-052/053 |
| 8 | Evidence factor screen IC | momentum/quality/value composite | 21d | **INCONCLUSIVE** — IC=0.011, CI spans 0; ships RESEARCH_ONLY | ADR-049 |
| 9 | Holdings discipline REDUCE flags | trend-health + Chandelier on own book | 21d fwd | **PENDING** ~mid-Jul 2026; TRIM already miscalibrated | ADR-048/051 |

Key cross-cutting lessons recorded in the ADRs:
- **Costs kill rotation** (#5: ~3.2 CAGR pts to monthly churn).
- **OOS halves in-sample edges** (#3: +9.2pp IS → +2.5pp OOS, CI spans 0).
- **Survivorship bias flatters** (#4 ran on survivor-biased universe and *still* failed; #7's clean smoke
  signal was a 4-year-window artifact). Honest coverage accounting is what killed #7.
- **Economic-relevance bar (|IC|≥0.02)** was pre-registered precisely to stop calling trivial-but-
  detectable effects "edge" — and it correctly killed #4 and #8.
- The one hypothesis with a *structural* (non-arbitrage) argument — #7, institutions can't fit into
  ~$300M names — is the only one that showed gross signal (+1.62%), but it dies on costs (150bps →
  +0.12% net) and needs **survivorship-complete paid data (CRSP/Sharadar)** for a definitive test.

## ML prediction infrastructure — exact break points

Models: `EnsemblePredictor` = XGB + LightGBM + Ridge (equal weight), per-horizon (2d/5d/10d), all with
`fit/predict/save_model/load_model`. Also `Stage2Predictor` (stacking, ADR-014) and `FlanT5Scorer` /
`KeywordScorer` (both `get_sentiment` is a `[]` stub — not wired to live data).

Six feature engineers exist (45 technical + 16 fundamental + 24 sentiment + 8 cross-asset + 8
event-causal + 8 smart-money). Smart-money engineer is **not** wired into the ensemble path.

Train → serve flow and the 3 missing links:

| Link | Status | Location |
|---|---|---|
| `_build_dependencies` loads a model | **MISSING** | `application/cli/_deps.py:24-70` |
| `PretrainingUseCase.execute` saves a model | **MISSING** | `application/use_cases.py:63-303` |
| `run-tournament` fits/loads before serving | **MISSING** | `ml_commands.py:63-89` |
| `_score_ticker` → predict on unfitted model | **RAISES NotFittedError** | `use_cases.py:458` |
| Error swallowed silently | present | `use_cases.py:373-375` |
| `*.model` artifacts on disk | **NONE EXIST** | `data/` |

Net: `run-tournament` emits 0 picks every run unless `pretrain` runs in the *same process* (it doesn't —
separate CLI command, fresh deps). Leakage guards: `FUTURE_LEAKAGE_COLUMNS` + `validate_feature_matrix`
run in pretrain only; `validate_point_in_time_access` is defined but **not called** in either use case;
the only active serve-path PIT guard is `YFinanceAdapter.validate_point_in_time` (blocks future-date fetch).

Universe: `config/tickers/sp500.txt` (500) + `nasdaq100.txt` (102) ≈ 602 dedup; filters min_mcap $2B,
min_vol 500k, no penny; 15-name hardcoded fallback in `_deps.py:191-207`.

## External sources + candidate surfacing — what exists

15 source adapters exist: yfinance (price/info/analyst), RSS (6 publishers), Google News RSS, Google
Trends (pytrends), GDELT, StockTwits (**DEPRECATED, 403 since 2026-06-05**), Reddit (disabled by
default), SEC EDGAR (13D/Form-4), SEC DERA Form-345 bulk, Wikipedia pageviews + resolver, AlphaVantage
news (neutral-stubbed in bulk scan), Finnhub analyst, Fama-French, earnings history.

Gemini (3 adapters): `GeminiNarratorAdapter` annotates *existing holdings* with cited-case summaries
(prompt forbids buy/sell/predict/winner words); `GeminiEventClassifier` classifies headlines but is
**inactive** in the live scan (`_compute_event()` hardcodes neutral 5.0); `gemini_models.py` = fallback
rotation. **Gemini never surfaces new tickers.**

Surfacing today (two paths):
- `screen-candidates` → `EvidenceScreenUseCase` over the static ~560-ticker file universe. No external discovery.
- `scan-opportunities` → `HybridUniverseProvider`: 28-ticker theme spine + RSS-discovered tickers, but
  only those already in the static ~120-name `_KNOWN_TICKERS` set. Thresholds (cmin=3, dmin=6) currently
  clear nobody on the warmed spine.

## What is ABSENT (factual)

1. No Morningstar integration (no API, no ratings, no "best stocks" lists).
2. No Google-Search / Google-AI "stocks to invest in" harvesting (GoogleNews adapter = News RSS only).
3. No web scraping (no BeautifulSoup/Selenium/Playwright/Scrapy); all ingestion via structured APIs/RSS.
4. No "top picks" editorial ingestion (Motley Fool, Zacks, Barron's, CNBC buy-lists, analyst aggregators).
5. No dynamic universe expansion from any externally-published recommended list.
6. No LLM-based candidate discovery — no LLM is asked to recommend/rank/surface tickers.
7. (Note: `scan-history.tsv` referenced in user memory does not exist in this repo; store uses SQLite
   `scan_candidates`/`surfaced_calls` tables.)

## Connections / data flow

`daily-scan` (RSS/Trends → SQLite buzz_signals) → `scan-opportunities` (conviction × divergence over
hybrid universe → SurfacedCall) and `screen-candidates` (factor IC screen → SurfacedCall) →
`resolve-calls` / `resolve-discipline-flags` forward-score against yfinance actuals → `weekly-brief`
composes holdings risk + discipline + regime + scorecard (RESEARCH_ONLY, attributed, no buy language).
`run-tournament` (dead ML path) sits outside this and produces nothing.
