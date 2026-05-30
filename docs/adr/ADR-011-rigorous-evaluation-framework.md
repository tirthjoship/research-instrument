# ADR-011: Rigorous evaluation framework — significance, walk-forward, cost-adjusted

**Date:** 2026-05-25
**Status:** Accepted
**Deciders:** Tirth Joshi

## Context
Original evaluation: Sharpe ratio, directional accuracy, precision/recall, SPY benchmark. This is better than most portfolio projects but missing critical rigor:

1. No statistical significance testing — can't distinguish skill from luck
2. Single train/test split — can overfit to specific market regime
3. No transaction costs — inflated return estimates
4. No regime decomposition — hidden beta exposure
5. No drawdown tracking — risk profile invisible

VanEck BUZZ ETF comparison showed that impressive-looking returns (42% 1-year) can mask poor risk-adjusted performance (1.65 beta). Our evaluation must be more honest.

## Decision
Phase 3A evaluation includes all five components:

### 1. Permutation tests for statistical significance
Shuffle predictions 1,000 times. Report p-value. Result is "real" only if p < 0.05.

### 2. Walk-forward validation
Train on months 1-N, predict month N+1. Slide forward. Never a single train/test split. Simulates real deployment.

### 3. Transaction cost modeling
Default 0.1% per trade (configurable). Subtract from all return calculations. Report gross AND net returns.

### 4. Regime-aware evaluation
Split results into bull (SPY >10% ann.), sideways (±10%), bear (<-10%). Report metrics per regime. If model only works in bull → capturing beta, not alpha.

### 5. Maximum drawdown tracking
Track: max drawdown, recovery time (days), worst single week. These determine real-world deployability.

## Alternatives Considered
- **Simple accuracy + Sharpe only** — insufficient for thesis validation and real-money decisions. Rejected.
- **Bayesian evaluation** — more sophisticated but harder to explain in interviews. Deferred.

## Consequences
**Positive:**
- Every result is quantified with confidence level.
- Can definitively say "model has edge" or "model got lucky."
- Interview story: "58.3% accuracy, p=0.007, cost-adjusted Sharpe 0.8 vs SPY 0.6."
- Required foundation for Phase 5-6 real-money deployment decision.

**Negative:**
- Permutation tests add ~30s to evaluation runs.
- Walk-forward produces fewer test predictions than single split.
- Accepted: rigor over convenience.

## Phase 3B Update (2026-05-30)

### 6. Three-way ablation study (new component)

Phase 3B adds a sixth evaluation component: ablation comparison across model variants.

Three variants run on identical folds and tickers:
1. **Technical-only** — Stage 1 frozen (Phase 3A baseline replay)
2. **Technical + sentiment** — Stage 2 with sentiment features, no source weighting
3. **Technical + sentiment + source weights** — Stage 2 full (source reliability-weighted sentiment)

Purpose: isolate what drives any observed lift. If variant 3 beats 2 beats 1, source reliability tracking adds value. If 2 ≈ 3, source weighting is noise. If 1 ≈ 2 ≈ 3, sentiment adds nothing — thesis falsified.

**Success threshold:** Sentiment must add ≥ 2% directional accuracy over Phase 3A's ~50% baseline. Below that, improvement is indistinguishable from noise given sample sizes.

## Superseded By
None
