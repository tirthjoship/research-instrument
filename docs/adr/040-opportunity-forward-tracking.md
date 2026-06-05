# ADR-040: Evidence-First Opportunity Surfacing & Forward-Tracking

**Date:** 2026-06-05
**Status:** Accepted
**Deciders:** Tirth Joshi

## Context

The conviction-validation work (ADR-038/039) tested the backtestable slice (smart-money 13D/insider + analyst — 2 of 8 dimensions). In-sample (2023-06→2026-05) the large-cap edge looked strong (bootstrap p=0.0005). **Out-of-sample (2018-01→2023-05, incl. 2020 crash + 2022 bear) it halved and lost significance** (bootstrap CI spanned 0, p=0.063); small/mid was negative. The late institutional signals are a faint, regime-sensitive lean — not a tradeable foundation.

The signals that catch emerging winners *early* (space: ASTS/RKLB/LUNR/IRDM; memory/storage: MU/WDC/SNDK) live in the **6 conviction dimensions held neutral in the backtest** (event-causal, sentiment/buzz, cross-asset/thematic, fundamentals). Those **cannot be backtested** — reconstructing point-in-time buzz/theme state is look-ahead bias. The only honest way to validate them is **forward-tracking live**.

Owner vision (carried from brainstorm): all-cap, do not tunnel to large-cap; catch winners early; buy *and* sell; the portfolio must beat S&P 500 *and* NASDAQ-100.

## Decision

Build **Leg-2 sub-project 1**: an evidence-first opportunity-surfacing + forward-tracking engine. Five locked decisions:

1. **Evidence-first** — surface + forward-track + accrue evidence. No portfolio construction yet.
2. **Hybrid all-cap universe** — curated thematic spine + dynamic buzz-discovery overlay.
3. **Multi-horizon forward-tracking** — each call tracked at 1w/1m/3m vs SPY *and* NDX; the cross-horizon shape is signal.
4. **Layered surfacing trigger** — conviction (8-dim quality) AND divergence (buzz-leads-price, "early"), with honest abstention.
5. **Approach 3** — thin, clean paper-call core (`SurfacedCall`/`CallOutcome`); reuse conviction engine, all 8 dims, `BuzzDiscovery`, `MultiHorizon`, Phase 8 `SignalPerformance` as-is.

## Alternatives considered

- **Portfolio-first** (jump to construction/sizing/two-sided) — rejected: builds on signals not yet forward-validated (the trap the validation work kept dodging).
- **Pure broad-index sweep** (Russell 3000) — rejected: data/SEC cost + noise; the hybrid overlay catches emerging names without the sweep.
- **7th UX redesign** — rejected: polishing presentation over substance.

## Consequences

- Paper-call semantics are kept **separate** from real-trade P&L (Phase 8 `TrackedTrade`).
- Evidence accrues over weeks/months — no instant validation; this is the cost of honestly validating un-backtestable signals.
- Portfolio construction, sizing, full two-sided discipline, and real-money execution are deferred to Leg-2 sub-project 2.
