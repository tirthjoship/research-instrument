# ADR-009: Add Ridge classifier to ensemble for model family diversity

**Date:** 2026-05-25
**Status:** Accepted (amends ADR-003)
**Deciders:** Tirth Joshi

## Context
Original ensemble: XGBoost + LightGBM averaged. Both are gradient boosting (same model family). They agree on 90%+ of predictions and disagree on exactly the hard cases where neither is reliable. This is not genuine ensemble diversity — it's the same algorithm twice with different implementations.

## Decision
Phase 3 ensemble: XGBoost + LightGBM + Ridge Classifier. Three models, two families (tree-based + linear). Weighted average by recent accuracy.

## Alternatives Considered
- **XGBoost + LightGBM only** — same family, correlated errors. Rejected.
- **Add neural network** — overkill for Phase 3, deferred to Phase 4 (LSTM-Transformer).
- **Random Forest instead of Ridge** — still tree-based, doesn't add family diversity. Rejected.

## Consequences
**Positive:**
- Genuine diversity: trees capture feature interactions, Ridge captures linear relationships.
- Uncorrelated errors improve ensemble performance.
- Ridge is fast, simple, regularized, low variance.
- ~30 lines of code to add.

**Negative:**
- Ridge may underperform trees on non-linear patterns.
- Accepted: weighted averaging means Ridge gets lower weight if it performs worse.

## Superseded By
None
