# ADR-015: Multi-horizon magnitude prediction with threshold-based classification

**Date:** 2026-05-25
**Status:** Accepted
**Deciders:** Tirth Joshi

## Context
Original target: `actual_5d_return` as binary up/down classification. Two problems:

1. **Binary is uninformative.** A stock up 0.01% and up 15% both classify as "up." A model that predicts tiny moves correctly is useless for investing. Need to predict *magnitude* and filter by actionable threshold.

2. **Fixed 5-day window is arbitrary.** Some signals play out in 2 days (news reactions), some in 2 weeks (value recovery). A single horizon forces all picks into the same timeframe, missing the natural duration of each signal type.

## Decision
Predict return magnitude across three horizons. Classify predictions as actionable only when they exceed noise thresholds.

### Target Variables (per ticker, per week)

| Horizon | Target | Noise threshold | What it captures |
|---------|--------|-----------------|------------------|
| 2-day | `predicted_return_2d` | ±1.5% | Short-term: news reaction, momentum |
| 5-day | `predicted_return_5d` | ±2.0% | Medium-term: divergence signal, trend |
| 10-day | `predicted_return_10d` | ±3.0% | Longer-term: value recovery, sector rotation |

### Classification from magnitude

| Predicted magnitude vs threshold | Class |
|----------------------------------|-------|
| Above positive threshold | Bullish (actionable buy signal) |
| Within ±threshold | Neutral (no action — signal is noise) |
| Below negative threshold | Bearish (actionable sell/avoid signal) |

### Grading logic (combines horizons)

| Grade | Criteria |
|-------|----------|
| Strong Buy | Bullish on 2+ horizons AND magnitude > 5% on longest bullish horizon |
| Buy | Bullish on 1+ horizon AND magnitude > threshold |
| Hold | Neutral on all horizons OR conflicting signals across horizons |
| May Sell | Bearish on 1+ horizon |
| Immediate Sell | Bearish on 2+ horizons AND magnitude > -3% |

### Model architecture impact

Stage 2 outputs three magnitude predictions (one per horizon), not one. Implementation options:

- **Option A (recommended for Phase 3):** Three separate lightweight models, one per horizon. Simple, interpretable, each can be evaluated independently.
- **Option B (Phase 4+):** Multi-task neural network with shared feature extraction and three output heads. More parameter-efficient but harder to debug.

Phase 3 uses Option A. Each horizon model is: XGBoost + LightGBM + Ridge ensemble → magnitude prediction.

### Hold duration derivation

The multi-horizon predictions naturally suggest optimal hold duration:
- Bullish at 2d but neutral at 5d → short hold (2-3 days)
- Neutral at 2d but bullish at 10d → longer hold (5-10 days)
- Bullish at all horizons → strong conviction, hold until first horizon flips

This replaces the need for a separate hold-duration prediction model (was planned for Phase 4). The multi-horizon approach gives it for free.

## Alternatives Considered
- **Binary up/down at 5 days** — treats 0.01% move same as 15% move. Uninformative. Rejected.
- **Single-horizon regression** — predicts magnitude but misses temporal dynamics. Rejected.
- **5+ horizons (1d, 2d, 3d, 5d, 10d, 20d)** — too many models for Phase 3, diminishing returns. Deferred.
- **Continuous confidence instead of threshold** — loses the "actionable vs noise" distinction. Rejected.

## Consequences
**Positive:**
- Model predictions are directly actionable ("buy now, expect +4% in 5 days")
- Noise-filtered: sub-threshold predictions are explicitly "no signal," not forced into buy/sell
- Hold duration emerges naturally from multi-horizon disagreement
- Each horizon is independently evaluable (which timeframe does model predict best?)
- Interview story: "I predict magnitude across three horizons and only act on statistically significant moves"

**Negative:**
- 3x models to train (one per horizon) — more compute
- Threshold selection is somewhat arbitrary (1.5%, 2%, 3%) — needs empirical tuning
- Mitigated: thresholds are configurable, tune via walk-forward after data accumulates
- Evaluation is more complex (precision/recall per horizon per threshold)
- Accepted: complexity is warranted by information gain

## Superseded By
None
