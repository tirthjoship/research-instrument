# ADR-038: Financial Intelligence Engine v1

**Date:** 2026-06-04
**Status:** Accepted
**Deciders:** Tirth Joshi

## Context

Phases 5.0–5.5 were six consecutive dashboard redesigns in three days. They polished the *presentation* of a conviction score that was never validated, while the only validated component — the technical ML model — backtests at coin-flip (5d accuracy 0.52, p=0.1464).

Three findings, verified in code, forced a pivot:

1. **The conviction score (dashboard centerpiece) has never been backtested** against forward returns. Its weights (`domain/conviction.py:79-84`) are hand-set magic numbers.
2. **The backtest fabricates its return metric:** `backtest_runner.py:98` is literally `model_excess_returns_per_fold = [a - 0.5 for a in accs]` — directional accuracy minus 0.5, relabeled as returns. `compute_sharpe_vs_spy` is defined but never called. This violates the project rule "Sharpe ratio, never accuracy alone".
3. **The Phase 4D event engine is dormant, not missing.** `EventCategory`, `gemini_event_classifier.py`, `event_impact_analyzer.py`, and `config/events/sector_mapping.yaml` already model `geopolitical` and `labor_layoffs`. It just isn't fed live news or wired into conviction.

Owner requirement: real-money use → **high precision, few false positives** ("winners only").

## Decision

Build a validated, precision-first **Financial Intelligence Engine v1**:

1. **Validation-first** — a real conviction backtest with a precision metric suite is the spine and the protected deliverable.
2. **Precision-first evaluation** — headline = **Top-Decile Hit Rate**; suite = precision@top-decile, monotonic precision–conviction curve, F₀.₅, expected-profit-per-signal, real Sharpe vs SPY. Accuracy banned as a headline.
3. **Revive the event engine** — feed it news, add a `government_investment` category, wire its output into conviction.
4. **Add independent free signals** — analyst upgrade/downgrade (Finnhub free + yfinance history), track-record-weighted.
5. **Learn the conviction weights** from historical precision.
6. **Honest UX** — hit-rate headline, per-pick evidence + confidence, abstention, signal-feedback panel. No tab restructure.

## Alternatives Considered

- **A 7th UX redesign (Phase 5.5 as written)** — rejected; polishing an unvalidated engine widens the confidence-vs-knowledge gap.
- **Meta-labeling, conformal prediction, options/short-interest squeeze radar, full-article LLM synthesis, Kelly sizing** — deferred to v2; not weekend-achievable and premature before validation.
- **Paid data (Bloomberg, TipRanks, Motley Fool premium)** — rejected; zero-budget constraint + ToS/legal red lines. Build a DIY analyst track-record scorer from free data instead.

## Consequences

- Net-new validation infrastructure (`precision_metrics.py`, `conviction_backtest.py`); the fabricated returns are removed.
- Conviction gains two new dimensions (`event_signal`, `analyst_signal`) and learned weights.
- Two new free data adapters (Alpha Vantage news, Finnhub analyst) behind new ports; CI uses fakes (no network).
- Validation may return a null (conviction ≈ random); that is reported honestly, and abstention protects against acting on noise.
