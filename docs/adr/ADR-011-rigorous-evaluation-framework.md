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

## Superseded By
None
