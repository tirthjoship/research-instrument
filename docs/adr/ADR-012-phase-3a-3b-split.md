# ADR-012: Split Phase 3 into 3A (pretrained technical) and 3B (live sentiment)

**Date:** 2026-05-25
**Status:** Accepted
**Deciders:** Tirth Joshi

## Context
Phase 3 scope expanded significantly during design review grilling session:
- 61 features (up from 44)
- Historical pretraining on 2-3 years
- Parallel NLP baselines
- Rigorous evaluation framework
- Ablation tracking
- Recursive learning with decay weighting

Single Phase 3 would be ~40% larger than original scope. Need clean separation.

## Decision
Split into two sub-phases:

### Phase 3A: Core Pipeline + Pretrained Model
- Full hex architecture (domain, ports, adapters, use cases)
- 45 features (technical + regime + options + sector + macro + cross-correlation — no sentiment)
- 2-3 year historical pretraining via yfinance
- XGBoost + LightGBM + Ridge ensemble
- Walk-forward validation + permutation tests
- Transaction cost modeling + regime evaluation + drawdown tracking
- CLI entry point + GitHub Actions
- SQLite storage
- Partial point-in-time mitigation (auto_adjust=False, known universe)

### Phase 3B: Sentiment Layer + Source Reliability (updated 2026-05-30)
- Keyword + Flan-T5 zero-shot parallel scorers (ADR-008)
- RSS feeds (6 publishers) + Reddit (PRAW). Google CSE + StockTwits deferred.
- 14 new features (revised from 25): buzz(2) + sentiment(5) + reliability(2) + divergence(3) + cross-signal(2) = 59 total
- Source reliability tracker baked in from day one (ADR-021)
- Daily buzz discovery scan + weekly full analysis (ADR-022)
- Three-way ablation: tech-only vs +sentiment vs +sentiment+source-weights
- Two-stage stacking: Stage 2 learns non-linear sentiment-technical interactions (ADR-014)
- Mid-cap universe expansion deferred to Phase 4
- CLI-only automation; cron/GitHub Actions deferred to Phase 4

## Alternatives Considered
- **Single Phase 3** — too large, hard to verify incrementally. Rejected.
- **Three sub-phases** — unnecessary granularity. Rejected.

## Consequences
**Positive:**
- Phase 3A ships working predictions independently.
- Phase 3A becomes the clean baseline for measuring sentiment lift.
- Each sub-phase is testable and deployable on its own.
- Clear "does sentiment add value?" answer from 3A vs 3A+3B comparison.

**Negative:**
- Two PRs instead of one.
- Accepted: smaller PRs are better anyway.

## Phase 3A Results (2026-05-29)

Phase 3A completed and merged (PR #4). Key outcomes:
- 45 features, 119 tests, 90.48% coverage
- Backtest: 40 S&P 500 mega-caps, Jan 2024 → May 2026, 19 walk-forward folds
- Results: ~50% directional accuracy (2d: 47.1%, 5d: 51.6%, 10d: 47.1%) — random baseline
- SHAP: 32/45 features near-zero importance, only 3 stable (correlation_with_spy, macd, macd_histogram)
- Confirms: technicals alone don't beat random on mega-caps (EMH expected)
- This is the clean baseline Phase 3B must beat by ≥ 2%

## Superseded By
None
