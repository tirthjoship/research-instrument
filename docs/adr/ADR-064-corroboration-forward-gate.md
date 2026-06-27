# ADR-064: Hypothesis #9 Pre-registered Forward Validation Gate

**Status:** Pre-registered (LOCKED — parameters must not change after first resolution run)
**Date:** 2026-06-23
**Lock date:** 2026-06-23 (this commit)
**Related:** ADR-048 (discipline forward-gate pattern), ADR-049 (RESEARCH_ONLY), ADR-051 (pre-registration), ADR-062 (corroboration engine), ADR-063 (blend formula)

## Hypothesis

> **STRONG-tier corroboration snapshots predict positive 21-day forward excess returns vs SPY.**

This is Hypothesis #9. Prior 8 alpha hypotheses: 1 NULL, 3 KILL, 3 INCONCLUSIVE, 1 RESEARCH_ONLY. All failed an honest out-of-sample bar.

## Why Pre-register

Harvested recommendations cannot be backtested — no historical snapshot exists prior to SP1 deployment. Forward-only is the only honest evaluation method. Pre-registering parameters before any resolution data accrues prevents p-hacking (adjusting the bar after seeing results).

**This ADR is the lock. Parameters below are immutable once any `resolve-corroboration` run completes.**

## LOCKED Gate Parameters

| Parameter | Value | Rationale |
|-----------|-------|-----------|
| Unit of observation | Per-ticker-snapshot `(ticker, snapshot_date)` pair | Reaches n=30 in ~3-5 weeks; within-ticker autocorrelation handled by block-bootstrap |
| Tier scope | STRONG only | MODERATE would dilute; top tier must earn its own badge |
| Primary statistic | Mean 21d excess return vs SPY | Consistent with discipline gate; interpretable |
| Statistical test | Moving-block bootstrap 95% CI on mean excess; lower bound must exceed 0 | Handles autocorrelation in time-series returns |
| Economic bar | 50 bps (0.005) mean 21d excess | ~12% annualised alpha; statistically significant but economically trivial results fail |
| Secondary metric | Hit rate (% STRONG beats SPY at 21d) — displayed only, not gated | Legibility |
| Secondary horizon | 63d mean excess — displayed only, not gated | Long-term framing |
| Minimum n | 30 resolved `(ticker, snapshot_date)` pairs | |
| Expected accrual time | ~3-6 weeks (depends on STRONG-tier count per run) | |
| Earliest evaluation | When n_resolved ≥ 30 AND all samples ≥21d old | |

## Verdict Logic

```
n_resolved < 30          → PENDING  (no verdict written)
n_resolved ≥ 30
  ci_lower > 0
  AND mean_excess_21d ≥ 0.005  → PASS
  otherwise                     → FAIL (permanent)
```

## KILL Clause

**FAIL is permanent.** If the gate evaluates to FAIL at n≥30, corroboration remains RESEARCH_ONLY indefinitely. No revival via collecting more data — that would be sequential p-hacking.

Revival is only permitted via a new, separately pre-registered ADR that:
1. Documents a structural reason why the initial evaluation period was invalid (e.g., confirmed data quality bug in SP1 during the accrual window)
2. Resets n=0 from a new lock date
3. Is committed before any new resolution data accrues

## On PASS

The `VALIDATED` badge unlocks in CLI output and dashboard (SP6). The equal-weight blend formula (ADR-063) may then be updated with IC-optimised weights — requires an ADR amendment before changing.

PASS does not mean "buy signal" — corroboration remains attributed evidence, not a prediction (ADR-062).

## Implementation Notes

- `domain/corroboration_gate.py` implements `evaluate_gate()` — pure, stdlib-only
- `data/corroboration_samples.jsonl` — append-only log of `GateSample` records
- `data/corroboration_gate_log.jsonl` — append-only log of `GateResult` records (written only when verdict ≠ PENDING)
- `resolve-corroboration` CLI — weekly job, idempotent
- `corroboration-calibration-status` CLI — read-only status display
- Source reliability learning loop deferred — `reliability_weight` stays static until gate resolves

## Deferred: Source Reliability Learning Loop

`HarvestedClaim.reliability_weight` is currently static (set at harvest time). A future spec will update per-source weights based on proven 21d forward hit-rates. This is deferred because:
1. If SP5 KILLs the signal, the learning loop was never needed
2. Feedback cycles with unvalidated weights add correctness risk before signal is proven

Future enhancement (tracked internally).
