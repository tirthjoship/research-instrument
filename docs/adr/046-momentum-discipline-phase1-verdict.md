# ADR-046: Momentum & Exit-Discipline Phase-1 Verdict — KILL (edge dead, drawdown-cut real)

**Date:** 2026-06-07
**Status:** Accepted
**Deciders:** Tirth Joshi
**Supersedes scope of:** Phase 2 of the ADR-045 plan (gated on PROCEED — not built)

## Context

ADR-045 pivoted the engine from return prediction to exit discipline and locked a pre-registered Phase-1 gate before any screener/daily-feed (Phase 2) could be built:

> PROCEED iff the strategy beats buy-and-hold on **Sharpe** (bootstrap CI on the Sharpe difference excludes 0, positive) **AND** cuts max drawdown by **≥ 30%**, out of sample on US+TSX, 2018-01-01 → 2026-06-01. KILL → stop, same discipline as ADR-044.

Phase 1 was implemented (pure rule primitives → `MomentumExitBacktestUseCase` → verdict gate → `validate-momentum-discipline` CLI → `PortfolioVerdictUseCase` → `portfolio-verdict` CLI) with TDD. Frozen params: 200-day trend filter, 3×ATR(22) Chandelier trailing stop, 12-1 momentum, top tercile, monthly rebalance, long-only equal-weight.

### Two correctness bugs were found and fixed before the verdict was trustworthy

Both caught in review; both would have produced a flattering, invalid verdict.

1. **Wrong gate statistic.** The CLI computed the bootstrap CI on the mean daily *return* difference (`moving_block_bootstrap` over the diff series), not the pre-registered CI on the **Sharpe difference**. The spec explicitly disavows the raw-return test ("Raw CAGR may be lower… that is expected and acceptable; the thesis is risk-adjusted improvement"). Because the strategy ~ties buy-hold on raw return, the wrong statistic was near-zero by construction. Fixed with `sharpe_difference_bootstrap` — a paired block bootstrap that resamples **shared** index-blocks applied to both legs, preserving cross-leg correlation so the Sharpe-difference variance is correct.

2. **Transaction costs were structurally never charged.** `prev_held` was snapshotted at the end of the loop *after* the rebalance/stop logic had already mutated `held`, so day-over-day turnover was always 0 → zero cost regardless of trading. A weak `<=` test masked it. Fixed by snapshotting `prev_held` immediately after the daily return is booked and before rebalance, and strengthening the test to strict `<`. Costs charged at 5 bps/side on actual strategy turnover; buy-hold left costless (the user's do-nothing baseline — realistic and the most conservative direction).

## Decision

**Accept KILL. Phase 2 (screener / daily feed) is not built.** Same conditional discipline as ADR-044's Phase 5.

### The numbers (corrected gate, 570-ticker US+TSX universe, 2018–2026)

| | Sharpe | CAGR | max drawdown | Sortino |
|---|---|---|---|---|
| **strategy** | 0.83 | 13.08% | 22.83% | 1.14 |
| buy_hold | 0.88 | 16.24% | 38.18% | 1.24 |
| spy | 0.82 | 14.88% | 33.72% | 1.15 |

- Max-drawdown reduction = **40%** → **passes** the ≥30% leg.
- Sharpe-difference point estimate = **−0.0497** (negative), 95% block-bootstrap CI = **[−0.787, +0.616]**, p(diff ≤ 0) = **0.555** → **fails** the Sharpe leg.
- Gate is AND → **KILL**. Report: `data/reports/momentum_discipline_20260607.json`.

### Why KILL, honestly

- **Costs are decisive.** Charging realistic turnover costs dropped strategy Sharpe 1.00 → 0.83 and CAGR 16.2% → 13.1%. Monthly momentum rotation churns; the churn costs ~3.2 CAGR points. Costs do not abate in bear markets, so the bull-window caveat (spec caveat 4) does not rescue the result.
- **The edge was never significant.** Even pre-cost, the Sharpe-difference CI is wide and straddles zero (Sharpe is a noisy statistic). The apparent +0.12 Sharpe gap from the first run was sampling noise (p ≈ 0.55), not a real risk-adjusted edge.
- This is the **fourth** independent pre-registered falsification (ADR-039, ADR-043, ADR-044, ADR-046). The "retail-accessible public signal → tradeable alpha" thesis is unsupported across conviction, dimensions, divergence-IC, and now mechanical momentum/exit risk-adjusted return.

### What survives — and what we keep

- **Drawdown reduction is real and cost-robust:** 38% → 23% max drawdown (a 40% cut), surviving transaction costs. Trend-following does exactly one thing reliably — it exits sustained declines.
- The gate benchmark (disciplined buy-hold-*everything*) is **not the user's actual behavior** (holding individual losers to the bottom — RIVN −56%). Against his real behavior, exit discipline plausibly helps; the gate did not, and was not designed to, measure that.
- Therefore the honest product is a **discipline / decision-support tripwire** on the user's own holdings — `PortfolioVerdictUseCase` / `portfolio-verdict` CLI returning EXIT / TRIM / HOLD per position — framed explicitly as *"cuts drawdown; does not beat the market."* Not an automated alpha strategy. Consistent with the project's honest-evidence-aggregator-plus-abstention identity (ADR-039/041).
- The **validation harness is kept as protected baseline:** `sharpe_difference_bootstrap`, the cost-aware `MomentumExitBacktestUseCase`, the locked verdict gate, and the TSX-extended universe — a reusable, honest, cost-and-significance-aware backtest rig for any future pre-registered candidate.

## Consequences

- **Phase 2 does not exist.** No screener, no daily recommendation feed built on this gate. Reopening requires a new pre-registered hypothesis with its own locked gate and ADR — not tuning this one (that would be the p-hacking the pre-registration discipline exists to prevent).
- **Branch merged to `develop`** as a validation harness + honest discipline tool, KILL notwithstanding. Code is reviewed, typed, and covered (1241 tests).
- **One evidence-backed reopening direction** (optional, requires fresh pre-registration): costs were the killer, so a **lower-turnover** variant — trend-filter-only (no monthly momentum rotation), or quarterly rebalance, or wider stops — is the single direction with a real prior. It must clear a new LOCKED gate on held-out data, with multiple-testing awareness, before any Phase 2.
- **No real-money automation.** The personal layer is decision support the user acts on manually; `holdings.csv` stays local/gitignored.
