# ADR-050: Trend-Following Sleeve Falsification Verdict — INCONCLUSIVE (weak-but-real diversifier, under the bar)

**Date:** 2026-06-08
**Status:** Accepted
**Deciders:** Tirth Joshi
**Builds on:** ADR-045 (process-not-prediction pivot), ADR-046 (momentum/exit KILL — drawdown-cut real), ADR-039/043/044 (no retail prediction edge in public signals), ADR-049 (decision-support engine)
**Closes:** the 2026-06-08 trend-following-sleeve falsification spec/plan
**Evidence basis:** Hurst, Ooi & Pedersen (2017) *A Century of Evidence on Trend-Following Investing*; Moskowitz, Ooi & Pedersen (2012) *Time Series Momentum*; Faber (2007).

## Context

Five pre-registered tests had falsified *prediction* edges in public signals (ADR-039/043/044/046 + Engine Phase-A INCONCLUSIVE). A focused-research pass flagged cross-asset 12-month time-series-momentum trend-following as the **one untested published strategy** with a century of OOS evidence that (a) needs no prediction (mechanical rules), (b) is retail-accessible via liquid ETFs, (c) reuses our trend/cost/bootstrap infra, and (d) claims its value as *diversification, not alpha* — so the gate was drawdown/risk-adjusted, not raw return.

**The claim under test (pre-registered, LOCKED before any result):**

> Blending a 12-month TSMOM sleeve (long/flat, 7 liquid cross-asset ETFs — SPY/EFA/EEM/TLT/IEF/GLD/DBC — inverse-vol weighted) at a fixed 20% with an 80% SPY core improves the **blended** portfolio's Sharpe **OR** cuts its max drawdown by ≥25%, net of 10bps cost, 2008–2026, vs 100% SPY.

**Frozen gate (spec §5):** PASS if Sharpe-diff bootstrap CI excludes 0 (positive) OR drawdown reduction ≥25%. KILL if blended is strictly worse on both axes (lower point Sharpe AND deeper drawdown). INCONCLUSIVE otherwise.

Built inline (TDD): pure-domain `trend_following.py` (momentum / inverse-vol / turnover / blend / equity-curve) + `TrendSleeveBacktestUseCase` (point-in-time monthly loop, look-ahead-safe, reusing `sharpe_difference_bootstrap` / `DrawdownTracker` / `backtest_metrics`) + `backtest-trend-sleeve` CLI. 1343 tests, 93.74% coverage, `make check` green. A gate-math review (dd_reduction sign, Sharpe-diff CI branch, KILL condition, no-look-ahead in `build_series`) found **no bug** — the implementation matches spec §5 verbatim.

## Decision

**Accept INCONCLUSIVE. Trend-following is NOT promoted to a validated engine feature. The discipline engine (ADR-047/048) remains the terminal bet.** Phase 2 (surfacing a sleeve allocation in the weekly brief) is gated on a PASS and is **not built**.

### The numbers (live, 7 ETFs, 2008-01 → 2026-01, 216 months, net of 10bps)

| Arm | Sharpe | max drawdown | CAGR |
|---|---|---|---|
| SPY-core (benchmark) | 0.748 | −46.1% | 11.5% |
| standalone sleeve (context) | 0.723 | **−8.0%** | 3.8% |
| **blended 80/20 (under test)** | **0.780** | −38.2% | 10.1% |
| 60/40 sensitivity (not gated) | 0.821 | −29.5% | — |

- **Sharpe-diff (blended − SPY):** point **+0.0319**, 95% bootstrap CI **[−0.0011, +0.0583]**.
- **Drawdown reduction:** **17.1%** (gate ≥25%).

Report: `data/reports/trend_sleeve_2026-06-08.json`.

### Why INCONCLUSIVE and not PASS

- **Primary (Sharpe) misses by a hair.** The CI lower bound is −0.0011 — it includes zero by 0.0011. Roughly ~96–97% of the bootstrap mass sits above zero, but pre-registration is pre-registration: a CI that spans 0 is not a PASS, full stop. And even if it cleared, **+0.032 Sharpe is economically tiny** — the diversification benefit at a 20% weight is real but marginal. I do not get to celebrate the near-miss.
- **Secondary (drawdown) misses cleanly.** 17.1% < 25%. The blend softened the worst drawdown (GFC) but only modestly, because the sleeve is only 20% of the book.

### Why INCONCLUSIVE and not KILL

The sleeve is demonstrably **not useless**: blended Sharpe is *higher* than SPY (0.780 > 0.748) and the drawdown is *shallower* (−38.2% > −46.1%). It is strictly worse on **neither** axis, so KILL would be dishonest. This is a genuinely different result from ADR-044 (dead signal) — here the diversifier works, it just doesn't clear the pre-registered bar at this weight on this sample.

### Regime read (the diversifier question)

The standalone sleeve's max drawdown is **−8.0% vs SPY's −46.1%** — the trend overlay successfully rotated to cash / safe-havens (TLT) during the sustained 2008–09 downtrend. That is exactly the TSMOM "crisis-alpha" behavior the literature documents, and it is the source of the 17.1% blended drawdown cut. Honest caveat, not measured directly in this run (the report gives full-sample maxDD only, not per-event sub-drawdowns): TSMOM with a 12-month lookback and monthly rebalance is **structurally too slow to dodge a fast crash (2020)**, and in 2022 the safe-haven bond leg fell with equities (the commodity/cash legs would have carried any protection). So the protection is regime-dependent — strong in slow grinding bears, weak in V-shaped crashes. The single largest event in the window (GFC) is a slow bear, which flatters the full-sample drawdown comparison.

### Is the drawdown-cut cost-robust?

Yes, at the tested 10bps/side. The 17.1% cut and the +0.032 Sharpe are already net of cost; the cut is a **structural** property (going to cash in downtrends), not a high-churn signal, so it is relatively cost-insensitive. It would erode at materially higher real-world costs, but 10bps is reasonable for these liquid ETFs.

### Does the standalone sleeve drag too much?

The trade at 20%: you give up **~140bps/yr CAGR** (11.5% → 10.1%) to buy a 7.9pp drawdown reduction and +0.032 Sharpe. Notably the **60/40 sensitivity has the best Sharpe of all configs (0.821) and a −29.5% drawdown** — i.e. more sleeve → better risk-adjusted outcome, suggesting the 80/20 simply *under-allocates* to a real diversification benefit. This is suggestive, **not actionable**: 60/40 was not the pre-registered allocation and cannot be claimed; treating a non-gated sensitivity sweep as the result is exactly the retuning the lock-before-run discipline forbids.

## Consequences

- **Trend-following is off the table as a *validated* feature.** Honest framing: it is a real, literature-consistent diversifier that did reduce drawdown — it just did not clear our own pre-registered bar at 20%/2008–2026. This is the **6th convergent "no robustly-clearing edge"** result, consistent with everything prior: standard public strategies do not hand this retail user a cleanly validated edge.
- **The discipline / risk decision-support engine (ADR-047) stays the terminal bet.** Its forward-calibration gate (ADR-048, due mid-late July 2026) is unaffected and remains the live trust gate.
- **Kept as protected baseline:** `domain/trend_following.py`, `TrendSleeveBacktestUseCase`, and `backtest-trend-sleeve` — a reusable, look-ahead-safe TSMOM/diversifier rig for any future re-test (e.g. a pre-registered 60/40 or a regime-conditioned allocation), should the user ever choose to commit to that as a *risk feature*, never as alpha.
- **No product, no portfolio integration, no brief surfacing** built — all were PASS-gated.

## Honest non-claims

INCONCLUSIVE does not mean "trend-following doesn't work" (it cut the worst drawdown by 17% and improved point Sharpe). It means **we did not earn the right to ship it as a validated diversifier** under the rules we set ourselves before the run. The label is not stronger than the evidence.
