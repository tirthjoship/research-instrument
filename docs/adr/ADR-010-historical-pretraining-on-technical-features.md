# ADR-010: Historical pretraining on 2-3 years of technical + regime features

**Date:** 2026-05-25
**Status:** Accepted
**Deciders:** Tirth Joshi

## Context
Phase 3 adds 61 features total (44 original + 7 stronger + 10 regime). With only live weekly data, it would take months to accumulate enough training rows (15 picks/week × ~6 months = ~360 rows). 61 features on 360 rows = overfitting.

Historical sentiment/buzz data is unavailable (RSS feeds show current content, Reddit coverage degrades historically). But technical + regime + options + sector features are fully available via yfinance for 2-3 years.

## Decision
Pretrain models on 2-3 years of historical data using technical + regime features only (no sentiment). This produces:
- 100+ weekly snapshots × 30-50 tickers = 3,000-5,000 training rows
- Healthy features-to-rows ratio for 36 features
- A clean baseline: "how well does price data alone predict?"

When live sentiment data starts flowing in Phase 3B, measure marginal lift of adding sentiment features over this pretrained baseline.

## Alternatives Considered
- **No pretraining, start from scratch** — insufficient data for 61 features. Rejected.
- **Use sentiment proxies (VADER on historical headlines)** — distribution shift when switching to live keyword/Flan-T5 scorer would pollute results. Rejected.
- **Reduce features to match available data** — loses valuable features. Rejected.

## Consequences
**Positive:**
- Solves features-vs-data tradeoff cleanly.
- Provides a built-in ablation: technical-only baseline vs full model.
- Directly tests thesis: "does sentiment divergence add value over technicals alone?"
- Models start with real knowledge, not random initialization.

**Negative:**
- Backtest subject to survivorship bias (yfinance only returns currently listed stocks).
- Mitigated by: known_universe snapshots, documenting the limitation.
- Historical OHLCV may have revision bias (splits, dividend adjustments).
- Mitigated by: `auto_adjust=False` for raw prices where possible.

## Superseded By
None
