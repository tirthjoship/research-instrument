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
- **Caveats:** only 2 of 8 conviction dimensions are historically reconstructable (smart-money + analyst); the other 6 (events, sentiment, fundamentals, ml_direction, signal_agreement, temporal_freshness) were held at neutral to avoid look-ahead bias, **and analyst firm-accuracy weighting was inactive** (empty firm-score map). So the validated quantity is the **smart-money + analyst slice, not the full conviction engine**. Small-cap list has survivorship bias.

## Consequences

- The system abstains (no pick surfaced) when no signal clears the conviction bar, rather than generating low-confidence picks.
- **Next directions (to be decided next session):**
  - Densify signal and add statistical power — more signal sources, longer history, more tickers.
  - Forward-track the event + sentiment-spike layer via existing outcome-tracking infrastructure; these signals cannot be cleanly backtested historically, but live outcomes can accumulate evidence over time.
  - Do not chase small-caps — the data does not support that hypothesis; focus on large-caps where the faint signal resides.
- The fabricated `accuracy - 0.5` returns metric is permanently removed. Any future return metric must compute real Sharpe vs SPY from actual position-level returns.
- ADR-038 validation infrastructure (`precision_metrics.py`, `conviction_backtest.py`) is the protected baseline for all future conviction claims.

## Update 2026-06-04 (later) — significance methodology corrected

A methodology review found the p-values in the table above are untrustworthy in **both** directions:

1. **Wrong null.** `compute_binomial_pvalue` tested against 0.5, but "win = beat SPY" and the empirical base rate of a signal-bearing name beating SPY in this universe is ~48%, not 50%. Testing vs 0.5 **understates** the edge.
2. **Within-date clustering.** Top-decile picks on the same scan date share that date's market window, so they are not independent Bernoulli trials. The binomial test treated them as independent, which **overstates** significance.

Fixes (branch `feat/conviction-validation-honesty`, no new data collected):

- `compute_binomial_pvalue` gained a `null_p` parameter; `run_conviction_backtest` now passes the empirical `base_rate` as the null and reports `base_rate`, `edge_over_base`, and `p_value_vs_50` for transparency.
- Added `date_level_significance`: collapses each scan date to one top-decile basket excess return vs SPY and runs a one-sided t-test, Wilcoxon signed-rank, and sign test on that near-independent series. **`date_level` is now the honest significance reading**, not the binomial `p_value` (which remains clustered by construction).

The headline cohort figures will be re-run under the corrected methodology before any further product decision. If the corrected reading is "promising but underpowered," the deferred fallback is densification (extend history, moving-block bootstrap, Deflated Sharpe) — not tighter scan-date spacing, which would manufacture significance via overlapping forward windows.

## Final results 2026-06-05 — corrected methodology + robustness + out-of-sample

Re-ran under the corrected methodology, then added F1 (concentration) + F2 (moving-block bootstrap), then F4 (out-of-sample). Large-cap cohort, signal-bearing, 21-day horizon:

| Test | In-sample 2023-06→2026-05 (34 dates) | OOS 2018-01→2023-05 (65 dates) |
|---|---|---|
| edge over empirical base rate | +9.2pp | +2.5pp |
| date-level t-test | 0.012 | 0.052 |
| date-level Wilcoxon | 0.042 | 0.070 |
| date-level sign test | 0.30 | 0.13 |
| mean excess / date | +3.58% | +1.96% |
| moving-block bootstrap CI (mean) | **[+1.4%, +6.9%]** | **[−0.5%, +4.7%]** |
| bootstrap p(mean ≤ 0) | **0.0005** | **0.063** |
| top-3-date concentration | 43.5% (broad) | 40.6% (broad) |

**Findings:**

- **In-sample the large-cap edge is robust** (bootstrap p=0.0005, CI floor +1.4%) and **broad** — top-3 dates contribute only 43.5% of gains, so it is NOT a few-lucky-months artifact. The sign-test "failure" (only 56% of dates positive) reflects a positive-expectancy, asymmetric-payoff profile (wins bigger than losses), not noise.
- **Out-of-sample the edge does NOT survive.** It halves (+2.5pp, mean +1.96%) and loses significance — the bootstrap CI now spans zero (p=0.063), t-test borderline (0.052). The 2023-26 strength was **partly bull-regime inflation**; the OOS window includes the 2020 crash and 2022 bear.
- **Small/mid-cap is negative OOS** (−10pp edge): definitively dead.
- The absolute +3.58%/3wk in-sample (~44% annualized) is an **optimistic upper bound** inflated by current-ticker survivorship (the 40 "large-caps" are today's winners) and one bull regime. The survivorship-robuster measure is the within-universe ranking edge (`edge_over_base`), which also weakens OOS.

**Verdict:** the backtestable institutional-signal slice (smart-money + analyst, 2 of 8 dimensions) is a **faint, regime-sensitive lean — not a tradeable foundation.** Best signal the project has produced (everything prior was coin-flip), but the sample flatters it and it fails out-of-sample.

**Decisions:**
- **F3 (Deflated Sharpe) skipped** — moot once OOS delivered the verdict; deflating a non-robust in-sample Sharpe adds nothing.
- **No real-money use** of this slice. Do not chase small-caps.
- **Pivot to forward-tracking** the early multi-dimensional thematic signals that cannot be backtested — implemented as Leg-2 (see ADR-040). This validation infrastructure (`precision_metrics.date_level_significance`, `moving_block_bootstrap`, the corrected null) is the protected baseline for all future conviction claims.
