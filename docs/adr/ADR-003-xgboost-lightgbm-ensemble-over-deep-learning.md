# ADR-003: XGBoost + LightGBM ensemble over deep learning

**Date:** 2026-05-23
**Status:** Accepted
**Deciders:** Tirth Joshi

## Context
Needed ML model for stock return prediction from 44 tabular features. Options included XGBoost alone, LightGBM alone, LSTM, Transformer, or ensemble.

## Decision
XGBoost + LightGBM simple average ensemble for Phase 3. LSTM-Transformer hybrid parked for Phase 4.

## Alternatives Considered
- **LSTM** — captures temporal sequences but needs different data format, harder to explain, overfits easily.
- **Transformer** — overkill for 15 stocks/week, heavy compute.
- **Single model** — misses easy ensemble lift.

## Consequences
**Positive:**
- Gradient boosting is king for tabular data (validated by 2026 research).
- SHAP explainability for every pick.
- Fast training on GitHub Actions.
- Two models = instant A/B comparison.

**Negative:**
- Cannot learn sequential patterns (e.g., "RSI dropped 3 consecutive weeks").
- Requires manual temporal feature engineering.
- LSTM in Phase 4 addresses this.

## Superseded By
None
