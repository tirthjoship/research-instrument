# ADR-014: Two-stage stacking model with decay weighting and retrain strategy

**Date:** 2026-05-25
**Status:** Accepted
**Deciders:** Tirth Joshi

## Context
Three interrelated problems identified during design review:

1. **Cold-start on sentiment features:** Pretrained model uses 41 technical/regime/macro features. When 25 sentiment features arrive in Phase 3B, model has never seen them. Retraining from scratch on all 66 features with limited data throws away 2-3 years of pretrained knowledge.

2. **Decay weighting calibration:** Recursive learning needs recent outcomes weighted more than old ones (markets are non-stationary). But no principled starting point for decay rate.

3. **Retrain vs fine-tune tradeoff:** Full weekly retrain is expensive and forgets learned patterns. Pure incremental update can drift. Need stage-appropriate strategy.

## Decision

### Two-Stage Stacking Architecture

```
Stage 1: Pretrained Technical Model
  Input:  41 features (technical + regime + macro + options + sector + cross-correlation)
  Output: predicted_return_technical, confidence_technical
  Training: 2-3 years historical data (3,000-5,000 rows)
  Status: FROZEN after pretraining (retrained monthly)

Stage 2: Sentiment Blending Model
  Input:  Stage 1 outputs (2 features) + 25 sentiment/buzz/divergence features = 27 features
  Output: final_predicted_return, final_confidence
  Training: 90-day backfill + live weekly accumulation
  Status: WARM-STARTED weekly, full retrain monthly
```

**Why stacking over joint training:**
- Stage 1 preserves 2-3 years of learned technical patterns
- Stage 2 only learns marginal lift of sentiment — simpler task, needs less data
- 27 effective features in Stage 2 (not 66) — healthy ratio with 360-600 initial rows
- Clean ablation: Stage 1 alone vs Stage 1+2 = exact sentiment contribution
- Standard ML technique (Wolpert 1992 stacked generalization)

### Decay Weighting

Starting half-life: **8 weeks** (configurable).

| Weeks ago | Weight |
|-----------|--------|
| 0 (this week) | 1.00 |
| 4 | 0.71 |
| 8 | 0.50 |
| 12 | 0.35 |
| 16 | 0.25 |
| 24 | 0.13 |

Implementation: `weight = 0.5 ** (weeks_ago / half_life)` passed as `sample_weight` to XGBoost/LightGBM/Ridge.

After 3 months of live data, optimize: compute walk-forward accuracy for half-lives [4, 6, 8, 10, 12] weeks. Best performer becomes tuned value.

### Retrain Schedule

| Component | Frequency | Method | Trigger for full retrain |
|-----------|-----------|--------|--------------------------|
| Stage 1 (technical) | Monthly | Full retrain on all historical data | New month begins |
| Stage 2 (blending) | Weekly | Warm-start from previous week's model | 3 consecutive weeks of degraded accuracy |
| Stage 2 (blending) | Monthly | Full retrain on top of new Stage 1 | After Stage 1 monthly retrain |

XGBoost warm-start: `xgb.train(params, dtrain, xgb_model=previous_model)`
LightGBM warm-start: `lgb.train(params, dtrain, init_model=previous_model)`
Ridge: full retrain always (fast enough, no warm-start needed)

### 90-Day Sentiment Backfill

Before Phase 3B goes live, backfill ~90 days of sentiment data:
- RSS feeds: 30-90 days of archived articles
- Reddit (PRAW): search history with decent coverage
- StockTwits: recent posts via API
- Google CSE: finds articles still on web

Produces 12 weekly windows × 30-50 tickers = 360-600 rows with sentiment features.

**Known limitations of backfill:**
- Buzz volume is approximate (deleted posts, changed rankings)
- Trending data from 60+ days ago is unavailable
- Features are directionally useful but magnitude is noisy
- Documented as limitation in evaluation output

## Alternatives Considered
- **Joint training on all 66 features** — throws away pretrained knowledge, overfits on small sentiment dataset. Rejected.
- **Separate models (no stacking)** — lose information flow between technical and sentiment signals. Rejected.
- **4-week half-life** — too aggressive, overfits to noise. Rejected as default (kept as tuning option).
- **No warm-start (full retrain weekly)** — expensive, forgets recent fine-grained patterns. Rejected for Stage 2.

## Consequences
**Positive:**
- Pretrained knowledge preserved indefinitely.
- Sentiment contribution measurable from day one (thanks to 90-day backfill).
- Decay weighting adapts to market regime changes.
- Retrain schedule matched to data availability at each stage.
- Self-tuning: half-life optimized empirically after 3 months.

**Negative:**
- Two-stage adds architectural complexity.
- Stage 2 predictions depend on Stage 1 quality — error propagation risk.
- Mitigated: Stage 1 is trained on 3,000+ rows with walk-forward validation — stable.
- 90-day backfill has known noise — documented, not hidden.

## Superseded By
None
