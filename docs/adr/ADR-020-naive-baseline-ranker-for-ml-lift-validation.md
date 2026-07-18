# ADR-020: Naive Stock-Selection Baselines for Validating ML Lift

**Status:** Accepted (backfilled 2026-07-17 — implemented earlier, never written up)
**Related:** ADR-011 (rigorous evaluation framework)

## Context

An ML model that "beats the market" means nothing on its own — the real
question is whether it beats trivial, non-ML selection rules. Without a
naive baseline, a positive backtest result could just be capturing a
well-known factor (momentum, low-volatility) that a two-line ranking rule
would have found for free.

## Decision

`application/evaluation.py::BaselineRanker` implements three naive,
zero-ML selection rules that every model result must be compared against:

- **`momentum`** — top N by 6-month return (the strongest documented
  equity factor; if the model can't beat this, its features aren't adding
  anything momentum doesn't already capture).
- **`low_volatility`** — top N by lowest 20-day volatility (a defensive
  selection rule, tests whether the model is just proxying for risk
  avoidance).
- **`random_selection`** — most frequently selected ticker across N
  seeded random trials (the floor: any result must beat pure chance).

## Consequences

**Positive:** Every ML lift claim in this project's evaluation framework
has an honest floor to clear, not just "better than nothing." Prevents the
common failure mode of a model appearing to work because it rediscovered
momentum.

**Negative:** `BaselineRanker` has no call sites outside its own test file
today — it's a manual research tool invoked during evaluation runs, not
wired into any automated CI gate. A future ADR should decide whether
baseline comparison should be a hard gate on new model claims rather than
a discretionary check.
