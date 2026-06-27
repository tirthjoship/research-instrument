# Spec Brief — SP5: Hypothesis #9 Pre-registered Forward Validation Gate

**Status:** Design brief (needs its own brainstorm → full spec → plan before coding)
**Depends on:** SP1 (weekly snapshots in `CorroborationStore`)
**Date:** 2026-06-20

## Purpose
Answer honestly: **does high corroboration forward-beat SPY?** This is the 9th alpha hypothesis (8 prior
ALL failed — research doc). It MUST be pre-registered and forward-only — harvested recommendations cannot
be backtested (no historical snapshot). Mirrors the ADR-048 discipline forward-gate pattern.

## Scope (in)
- Pre-register a LOCKED gate BEFORE forward data accrues (anti-p-hacking, per ADR-051): e.g. STRONG-tier
  21-day forward return beats SPY by a bootstrap-CI-excludes-0 margin, n≥30 resolved, since-date locked.
- A `resolve-corroboration` weekly job: take prior snapshots, compute realized 21-day forward returns,
  update `source_reliability` hit-rates (the SP1 "it learns" loop), and accrue gate samples.
- A `corroboration-calibration-status` command (mirror `discipline-calibration-status`): READY when n≥30.
- On gate pass → a VALIDATED badge unlocks; on fail → corroboration stays RESEARCH_ONLY (KILL clause).

## Scope (out)
- No historical backtest of LLM-harvested recs (impossible). The SP1 dated-source sanity check is a
  separate, labelled, non-verdict signal.
- No live trading off the badge.

## Proposed approach
New `application/corroboration_forward_gate.py` + ADR pre-registering the gate (write the ADR BEFORE the
first resolution). Reuse the bootstrap/IC test utilities from the existing validation use cases
(`validate-divergence-ic`, `momentum_exit_backtest`). Schedule weekly resolution (launchd, like the
discipline job).

## Open questions
- Exact gate statistic + threshold (propose: STRONG-tier mean 21d excess vs SPY, block-bootstrap CI > 0,
  AND |excess| ≥ a pre-set economic bar; lock before data).
- Horizon(s): 21d primary (short), plus a 3-month secondary for "long-term" framing (exploratory).
- Minimum n and earliest-resolution date (propose n≥30, ~10-12 weeks of accrual).
- Pre-registration ADR number + lock date must be committed before any resolution runs.
