# ADR-013: Macro regime features in Phase 3A, portfolio correlation constraints in Phase 4

**Date:** 2026-05-25
**Status:** Accepted
**Deciders:** Tirth Joshi

## Context
Model treats each stock as independent prediction. But stocks move in correlated clusters driven by macro environment. 15 recommendations could be 80% correlated — one macro event crashes all simultaneously. Two distinct problems:

1. No macro environment awareness (model doesn't know "risk-off environment, discount bullish signals")
2. No portfolio-level diversification constraint (top 15 by score may all be tech/AI stocks)

## Decision

### Phase 3A: Add 5 macro regime features
All free via yfinance. Applied globally (same values for all tickers in a given week):

| Feature | Ticker/Source | What it captures |
|---------|--------------|-----------------|
| `vix_level` | ^VIX | Market fear / volatility regime |
| `treasury_10y_direction` | ^TNX | Rate environment (rising = risk-off) |
| `dxy_strength` | DX-Y.NYB | Dollar strength (affects multinationals) |
| `yield_curve_slope` | ^TNX - ^IRX | Recession predictor (inverted = danger) |
| `spy_momentum_20d` | SPY | Overall market trend |

These are the same 5 values for every ticker in a given week — they contextualize the entire prediction environment.

### Phase 4: Portfolio correlation constraints
When selecting top 15, enforce:
- Maximum pairwise correlation of 0.7 between any two picks
- Maximum 30% weight in any single sector
- Sector diversity: minimum 3 sectors represented

This requires correlation matrix computation and constrained optimization — more infrastructure than Phase 3A scope.

## Alternatives Considered
- **No macro features** — model blind to environment. Rejected.
- **Macro features in Phase 3B** — they're price-based, not sentiment-based. Belong in 3A. Rejected.
- **Correlation constraints in Phase 3A** — requires correlation infrastructure. Deferred to Phase 4.
- **Sector caps only (no correlation)** — sector is a proxy for correlation but misses intra-sector diversity. Rejected as insufficient, but sector caps added as Phase 4 complement.

## Consequences
**Positive:**
- Model learns "bullish divergence in risk-off environment = less reliable."
- 5 features, zero engineering complexity — just 5 more yfinance pulls.
- Available for full 2-3 year pretraining window.
- Phase 4 correlation constraints prevent concentration risk for real-money deployment.

**Negative:**
- 5 global features (same for all tickers) may confuse per-ticker models.
- Mitigated: tree models handle mixed global/local features well.

## Superseded By
None
