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
- 36 features (technical + regime + options + sector — no sentiment)
- 2-3 year historical pretraining via yfinance
- XGBoost + LightGBM + Ridge ensemble
- Walk-forward validation + permutation tests
- Transaction cost modeling + regime evaluation + drawdown tracking
- CLI entry point + GitHub Actions
- SQLite storage
- Partial point-in-time mitigation (auto_adjust=False, known universe)

### Phase 3B: Live Sentiment Layer
- Keyword + Flan-T5 zero-shot parallel scorers
- RSS, Google CSE, Reddit, StockTwits adapters
- 25 additional features (sentiment/buzz/divergence)
- Ablation: technical-only vs sentiment-only vs combined
- Recursive learning with decay weighting
- Marginal lift measurement vs Phase 3A baseline

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

## Superseded By
None
