# ADR-048: Pre-Registered Forward-Calibration Gate for the Discipline Flags (+ TRIM is not a down-call)

**Date:** 2026-06-08
**Status:** Accepted
**Deciders:** Tirth Joshi
**Builds on:** ADR-046 (momentum/exit KILL — drawdown-cut real, edge dead), ADR-047 (alpha-hunt complete → discipline engine)

## Context

The Holdings Discipline & Risk Engine shipped (ADR-047) and produced its first evidence.

**Day-1 historical calibration** (`backtest-discipline-flags`, 2026-06-08, 5462 point-in-time
verdicts across the 66 real holdings, frozen params, point-in-time, cost-basis-free):

| Verdict | n | down-rate | mean fwd (21d) |
|---|---|---|---|
| REDUCE | 264 | **58%** | **−1.71%** |
| TRIM | 1976 | 43% | **+1.85%** |
| HOLD | 1295 | 39% | +0.96% |
| ADD_OK | 1163 | 39% | +1.14% |
| REVIEW | 764 | 36% | +3.59% |

Two findings drive this ADR:

1. **REDUCE discriminates** — 58% down-rate, −1.71% mean forward return, vs HOLD/ADD_OK at 39%
   and positive returns. The first non-KILL signal in the project. But it is **in-sample and
   optimistically biased**: the universe is survivor-biased (names still held), the 2018–26 window
   was mostly up, and the price paths were already visible. A report card on the past — not proof.

2. **TRIM is mis-framed.** TRIM names went **+1.85%** (up), yet the original calibration scored
   TRIM as a "down" assertion (p=1.0), inflating the combined Brier to 0.551 (~coin-flip).
   TRIM = "winner that breached its 3×ATR trailing stop" — in an uptrend those typically resume
   up. TRIM is a **position-sizing / lock-gains** action, not a directional prediction.

A separate caution from the same run: at the **index** level (`holdings-risk-calibrate SPY`),
"below trend" mean-reverted **up** (+2.37%). The REDUCE effect is **cross-sectional single-name
drift**, not index timing — which is exactly why the engine abstains (REVIEW) when the whole
market is broken (`market_trend_health` guard). The architecture already encodes this.

## Decision

**1. TRIM is excluded from the directional gate.** Only REDUCE is a down-call (p=1.0) and feeds
the Brier. TRIM is tracked separately (`trim_resolved`, `down_rate_on_trim`) for transparency and
its narration is reframed to "manage size / lock gains — not a prediction the name will fall."
(Implemented: `resolve_flags`, `backtest_discipline_calibration` → `brier_reduce`/`n_reduce`,
`template_narration`.)

**2. Pre-register the forward-calibration gate — LOCKED before any forward data accrues.**
The historical 58% is not the gate; the gate is out-of-sample on the real book going forward:

> **Universe:** REDUCE flags logged on/after **2026-06-08** in `data/personal/discipline_log.jsonl`
> (the clean, dated, prospective log).
> **Horizon:** 1 month (21 trading days).
> **Resolver:** `resolve-discipline-flags --horizon 21`.
> **PROCEED bar (all three):** down_rate_on_reduce **≥ 55%** AND **brier ≤ 0.45** AND
> **n (resolved REDUCE) ≥ 30**.
> **KILL clause:** if, once n ≥ 30 has accrued, the bar is not met, the discipline-flag layer is
> dropped honestly — same standard that killed ADR-039/043/044/046.
> **Excluded from the gate:** TRIM, HOLD, ADD_OK, REVIEW (not down-calls).

**3. No threshold tuning before the gate resolves.** The trend/ATR/Chandelier params stay FROZEN
(ADR-046). Tuning them to improve the in-sample report card is the exact overfitting the Deflated
Sharpe research (ADR-047 context) warns against. The gate judges the frozen rules.

**4. Phase-2 (factor screening) stays gated** on a PROCEED here — it does not start on in-sample
evidence.

## Consequences

- The engine's self-report is now truthful: it no longer claims TRIM predicts drops.
- The honest status is *"promising on historical evidence, unproven forward; value is risk/behavior,
  not return."* That earns a forward test — not a build-out, not abandonment.
- A daily scheduled `holdings-risk` run accrues the log; at ~4–6 weeks the gate has resolvable
  REDUCE flags and returns PROCEED or KILL.
- Honest caveat: even a PROCEED means "REDUCE flags precede single-name drops out-of-sample" — it is
  **not** proof the tool beats the user's behavior (that needs a logged trade baseline, deferred) nor
  that it beats buy-hold (ADR-046 already says it does not, risk-adjusted).
