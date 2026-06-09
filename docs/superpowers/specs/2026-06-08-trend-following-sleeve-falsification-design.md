# Trend-Following Sleeve — Falsification Test — Design Spec

**Date:** 2026-06-08
**Status:** Draft for review
**Author:** Tirth Joshi (with Claude)
**Builds on:** ADR-045 (process-not-prediction pivot), ADR-046 (momentum/exit KILL — drawdown-cut real), ADR-039/043/044 (no retail prediction edge in public signals)
**Evidence basis:** Hurst, Ooi & Pedersen (2017) *A Century of Evidence on Trend-Following Investing*; Moskowitz, Ooi & Pedersen (2012) *Time Series Momentum*; Faber (2007) *A Quantitative Approach to Tactical Asset Allocation*.

---

## 1. What this is — and what it is not

A **pre-registered falsification test** of one specific, published, retail-accessible strategy we have **not** yet tested: **cross-asset 12-month time-series momentum (trend-following), held long/flat via liquid ETFs, as a diversifying sleeve.**

- It tests trend-following in its **real published role** — a diversifying, drawdown-reducing, crisis-alpha sleeve — **NOT** as a return-maximizer or an alpha source. The honest claim is "does adding a small trend sleeve to an equity core improve risk-adjusted return or cut drawdown, net of cost," not "does trend-following beat the market."
- It is a **backtest only.** No sleeve product, no portfolio integration, no delivery is built in this phase. Those are gated on a PASS (a follow-on brainstorm).
- It follows the **same lock-before-run discipline** as every prior falsification (ADR-044/046): the gate is frozen before the first result; no re-tuning to manufacture a PASS.

**Why this strategy, why now:** five pre-registered tests have falsified *prediction* edges in public signals. A focused-research pass flagged cross-asset trend-following as the one strategy with a century of OOS evidence that (a) we have not directly tested, (b) requires no prediction (mechanical trend rules), (c) is retail-accessible via liquid ETFs, and (d) reuses our existing trend/cost/bootstrap infrastructure. Its honest value is diversification, not alpha — so the gate is drawdown/risk-adjusted, not raw return.

## 2. The claim under test (pre-registered)

> Blending a 12-month time-series-momentum trend sleeve (long/flat, liquid cross-asset ETFs, inverse-vol weighted) at a fixed 20% weight with an 80% SPY equity core improves the **blended** portfolio's risk-adjusted return (Sharpe) **or** cuts its maximum drawdown by ≥25%, net of transaction costs, over 2008–2026 — versus a 100% SPY buy-and-hold core.

This is a *blended-portfolio* claim, not a standalone-sleeve claim. Trend-following alone will likely underperform SPY on raw return (it sits in cash during equity bull runs); that is expected and is **not** the test.

## 3. Universe & data (drives the design)

**ETF universe (7 liquid, cross-asset, all with daily history ≥ 2007):**

| Ticker | Asset class |
|---|---|
| SPY | US equity |
| EFA | Developed-intl equity |
| EEM | Emerging-market equity |
| TLT | Long US Treasury |
| IEF | 7–10y US Treasury |
| GLD | Gold |
| DBC | Broad commodities |

**Window:** 2008-01 → 2026-01, monthly cadence. (12-month lookback uses 2007 data; first signal 2008-01.) This deliberately spans the 2008 GFC, 2020 COVID crash, and 2022 stock/bond drawdown — the regimes where trend-following is supposed to earn its keep. If it cannot help across those, it fails honestly.

**Data source:** `application.price_returns.load_price_series` (yfinance, leakage-safe, already used by every prior backtest). Risk-free / cash leg: a constant 0% (conservative — understates the sleeve's cash return, so a PASS is not inflated by a generous cash assumption). **Survivorship note:** these are the canonical major-asset-class ETFs; none has been delisted, so survivorship bias is negligible (unlike single-stock universes).

## 4. Signal & construction (LOCKED)

All steps run **point-in-time** at each month-end `t`; no data after `t` is used.

1. **Trend signal (per ETF):** trailing **12-month total return** (from adjusted closes, the existing loader's series) of the ETF as of `t`. If `> 0` the ETF is **trend-positive (held)**; if `≤ 0` it is **trend-negative (its slot goes to cash)**.
2. **Sizing — inverse-vol across ALL 7, then zero the negatives (canonical risk-parity trend, gives crisis protection):**
   - Compute a raw inverse-vol weight for **every** ETF: `w_i = (1/σ_i) / Σ_{j=1..7}(1/σ_j)`, where `σ_i` is the ETF's trailing 60-trading-day return volatility as of `t`. These 7 raw weights sum to 1.
   - **Zero out every trend-negative ETF** (`w_i → 0`); trend-positive ETFs **keep their raw inverse-vol weight** (they are NOT renormalized up to fill the gap).
   - The vacated weight becomes **cash**: `w_cash = Σ_{trend-negative i} w_i_raw`.
   - Consequence (the whole point): when most assets are in downtrends (e.g. 2008), most slots are cash and the sleeve is defensive; when all 7 trend up, `w_cash = 0` and the sleeve is fully invested.
3. **Sleeve monthly return:** `Σ_{i=1..7} w_i · r_i(t→t+1) + w_cash · 0`, where `r_i` is ETF `i`'s realized return over `t→t+1`, `w_i` is its (possibly-zeroed) weight from step 2, and the cash leg earns 0%.
4. **Costs:** charge `TransactionCostModel` (default 10 bps per unit turnover, one-way) on the **sleeve's** month-over-month weight turnover only. The SPY core is buy-and-hold (no turnover, no cost beyond an initial entry that applies equally to all arms and is ignored).
5. **Blended portfolio:** `0.80 · r_SPY(t→t+1) + 0.20 · r_sleeve_net(t→t+1)`, rebalanced monthly back to 80/20.

**Frozen parameters (no re-tuning):** universe (7 ETFs), lookback (12 months), vol window (60 days), blend (80/20), cost (10 bps), window (2008–2026), monthly cadence. A 60/40-style blend (e.g., 60% SPY / 40% sleeve) is reported as a **sensitivity only** — it does not move the gate.

## 5. Validation — the pre-registered gate (LOCK before first run)

Compute three return series, all monthly, net of cost: **SPY-core** (benchmark), **standalone sleeve** (context only), **blended 80/20** (the thing under test). Then:

- **Primary — risk-adjusted:** block-bootstrap **Sharpe-difference** (blended − SPY-core) via `precision_metrics.sharpe_difference_bootstrap` (monthly, `periods_per_year=12`).
- **Secondary — drawdown:** max drawdown of blended vs SPY-core via `evaluation.DrawdownTracker`; the **drawdown-reduction ratio** `1 − maxDD_blended / maxDD_SPY`.

**Outcome (frozen):**
- **PASS** if **either** the Sharpe-diff bootstrap CI **excludes 0 (positive)** **OR** the drawdown reduction is **≥ 25%** (`maxDD_blended ≤ 0.75 · maxDD_SPY`).
- **KILL** if the blended portfolio is **strictly worse** on both axes (lower point Sharpe **and** deeper max drawdown than SPY-core).
- **INCONCLUSIVE** otherwise (e.g., a drawdown cut < 25% with a Sharpe-diff CI spanning 0).

**Every report prints, net of cost:** standalone-sleeve / blended / SPY-core Sharpe, max drawdown, CAGR, and the Sharpe-diff point + CI + drawdown-reduction %. No metric is hidden; the label is never stronger than the evidence. The 60/40 sensitivity is printed beneath the primary result, clearly marked "sensitivity, not gated."

**Honest non-claims:** a PASS means trend-following is a worthwhile *diversifier sleeve* (risk control), **not** that it beats the market or generates alpha. The output says so explicitly.

## 6. Architecture (hexagonal, reuse-heavy)

```
domain/trend_following.py (NEW, pure stdlib)
  time_series_momentum(monthly_closes) -> float | None     # 12-mo total return
  inverse_vol_weights(vols: dict[str,float]) -> dict[str,float]
  blend_returns(core, sleeve, core_weight) -> list[float]
  turnover(prev_w, new_w) -> float

application/trend_sleeve_backtest.py (NEW)
  TrendSleeveBacktestUseCase
    - point-in-time monthly loop over the 7-ETF panel
    - reuses: price_returns.load_price_series, precision_metrics.sharpe_difference_bootstrap,
              evaluation.TransactionCostModel, evaluation.DrawdownTracker
    - returns SleeveVerdict(decision, sharpe_diff_point/ci, dd_reduction, per-arm Sharpe/maxDD/CAGR)

application/cli.py (MODIFY)
  backtest-trend-sleeve  ->  writes data/reports/trend_sleeve_<date>.json, prints full verdict
```

- **domain/** stays pure (stdlib only — the signal math is simple arithmetic). No look-ahead: the use case only ever passes the use case `closes ≤ t` into the domain functions.
- **application/** does the IO (price loading) and orchestration, reusing the protected falsification harness verbatim — no new statistical rig is invented.
- The panel builder mirrors the leakage-safe pattern already in `application/screen_ic_panels.py` (load full series per ticker once, slice point-in-time per month).

## 7. Testing

- `domain/trend_following.py`: unit + Hypothesis — `time_series_momentum` sign matches a constructed up/down series; `inverse_vol_weights` sums to 1 and down-weights the high-vol asset; `blend_returns` is the exact convex combination; `turnover` is 0 for an unchanged book and 2·|Δ| accounting is correct.
- `TrendSleeveBacktestUseCase`: a **planted fixture** where one ETF trends up strongly and equities crash mid-sample → the sleeve goes defensive and the blended portfolio's max drawdown is provably smaller than SPY-core (recovers the benefit); a **flat/noise fixture** where no asset trends → the sleeve sits in cash, the blend ≈ 80% SPY, and the gate does **not** false-PASS. Drawdown math verified against a hand-computed equity curve.
- Costs: a turnover-heavy fixture confirms costs are charged on the sleeve and reduce its return.
- `make check` green (mypy strict, ≥90% cov) before any live run.

## 8. Scope & exit gate

- **This phase is the test only.** No sleeve product, no portfolio overlay, no brief integration.
- **PASS** → brainstorm Phase 2 (how to surface the sleeve allocation in the weekly brief / portfolio — a *risk-management* feature, still no alpha claim).
- **INCONCLUSIVE** → report honestly; optionally note the 60/40 sensitivity; trend-following stays a documented "diversifier with weak/again-regime-dependent evidence," not built into the product.
- **KILL** → document in an ADR; trend-following is off the table; the process-edge (discipline engine + July gate) remains the project's terminal bet.
- **No re-tuning to rescue a result.** A failed gate is a result, recorded — the ADR-046 discipline.

## 9. Open questions for reviewer

1. Cash leg: constant 0% (conservative, chosen) vs an actual T-bill series (`^IRX`/BIL)? (Lean: 0% — a PASS that survives the conservative assumption is more credible; T-bill only inflates the sleeve.)
2. Blend weight: 80/20 primary with 60/40 sensitivity (chosen) — acceptable, or do you want a different primary (e.g., 90/10)? (Lean: 80/20 — standard diversifier sizing, pre-registered.)
3. Universe size: 7 ETFs (chosen) vs adding VNQ (REITs) / UUP (dollar)? (Lean: 7 — the canonical cross-asset set; more ETFs = more researcher-degrees-of-freedom to overfit.)
