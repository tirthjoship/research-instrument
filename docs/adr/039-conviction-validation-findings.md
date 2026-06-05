# ADR-039: Conviction Validation Findings & Product Framing

**Date:** 2026-06-04
**Status:** Accepted
**Deciders:** Tirth Joshi

## Context

ADR-038 mandated a validation-first pivot: build a leakage-safe conviction backtest harness and report what it finds honestly, including a null result. This ADR records the first powered, leakage-safe backtest result and the product framing decision that follows from it.

The backtest ran after:

1. **Fabricated returns metric removed** — `backtest_runner.py` was computing `accuracy - 0.5` and relabeling it "excess returns." That metric is gone. `compute_sharpe_vs_spy` is now called and reported; if it cannot be computed, an honest null is surfaced instead.
2. **Conviction backtest harness built** — stratified walk-forward (monthly steps, 21-day forward horizon). Metrics: Top-Decile Hit Rate, monotonic precision–conviction curve, F₀.₅, expected-profit-per-signal, real Sharpe vs SPY.
3. **Two conviction dimensions historically reconstructable** — smart-money (SEC EDGAR 13D + Form 4) and analyst upgrade/downgrade (Finnhub + yfinance). Events, sentiment, and fundamentals were held at neutral to avoid look-ahead bias.

Two tickers in the small/mid-cap cohort (CIVI, GMS) were dropped as delisted or unavailable during the backtest window.

## Decision

Frame the product as an **honest evidence-aggregator + calibrated-abstention tool**: surface organised, point-in-time evidence per name and abstain when nothing clears the conviction bar. Do not frame it as a beat-the-market predictor.

This framing is grounded in the findings below. Given a "credible-null-with-a-whisper" result, the appropriate response is to be explicit about what the system knows and does not know, and to decline to surface picks when evidence is thin.

## Findings (First Powered, Leakage-Safe Backtest)

**Setup:** Stratified walk-forward, 76 tickers, 2023-06 → 2026-05, monthly steps, 21-day horizon, top-decile signals only, signal-bearing tickers only.

| Cohort | Top-Decile Hit Rate | Excess Sharpe vs SPY | n (top-decile picks) | p-value |
|--------|--------------------|--------------------|---------------------|---------|
| Large-cap | 57.4% | +0.52 | 61 | 0.15 |
| Small/mid-cap | 48.6% | −0.52 | 35 | 0.63 |
| Overall | 56.1% | +0.39 | 98 | 0.13 |

**Interpretation:**

- **No statistically significant edge in any cohort** (all p > 0.13). Not tradeable as-is.
- A **faint, non-significant positive lean** overall (56.1%, p=0.13): "something, maybe" — not nothing, not a proven edge.
- The **small/mid-cap hypothesis was not supported** — it underperformed SPY (−0.52 excess Sharpe) despite survivorship bias in the small-cap list that should have flattered it. Any faint signal lives in large-caps.
- Top-decile sample sizes remain **modest** (61 / 35 / 98).
- **Caveats:** only 2 of 8 conviction dimensions are historically reconstructable (smart-money + analyst); events, sentiment, and fundamentals were held at neutral to avoid look-ahead bias. Small-cap list has survivorship bias.

## Consequences

- The system abstains (no pick surfaced) when no signal clears the conviction bar, rather than generating low-confidence picks.
- **Next directions (to be decided next session):**
  - Densify signal and add statistical power — more signal sources, longer history, more tickers.
  - Forward-track the event + sentiment-spike layer via existing outcome-tracking infrastructure; these signals cannot be cleanly backtested historically, but live outcomes can accumulate evidence over time.
  - Do not chase small-caps — the data does not support that hypothesis; focus on large-caps where the faint signal resides.
- The fabricated `accuracy - 0.5` returns metric is permanently removed. Any future return metric must compute real Sharpe vs SPY from actual position-level returns.
- ADR-038 validation infrastructure (`precision_metrics.py`, `conviction_backtest.py`) is the protected baseline for all future conviction claims.
