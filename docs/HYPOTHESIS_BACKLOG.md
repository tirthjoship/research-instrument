# Hypothesis Backlog — the hunt stays disciplined, not dead

> ADR-052 closed backtest-driven alpha hunting permanently. This backlog is the ONLY
> sanctioned path for future predictive ideas: an idea may graduate to code ONLY
> after every field below is filled in and committed BEFORE any data is examined.
> Forward evidence (gate, adherence, screen IC) accrues regardless — read it before
> proposing anything here.

## Entry bar (all fields mandatory, committed before code)

| Field | Requirement |
|---|---|
| Hypothesis | One falsifiable sentence ("X predicts Y over horizon H") |
| Pre-registered thresholds | Exact pass/fail numbers, locked in an ADR |
| Kill condition | What result kills it permanently (no re-runs, no tuning) |
| Data cost | Sources, fetch budget, point-in-time feasibility |
| Conflict check | Must not violate ADR-052 scope or wrap-plan §5 (no online learning) |

## Parked ideas

### Unit D — realized-slippage measurement (parked by wrap plan §6)
- **Hypothesis:** realized execution cost on sub-$1B names is materially below the
  assumed 150 bps, enough to flip Unit B's net verdict.
- **Preconditions if ever revived:** Unit B INCONCLUSIVE with gross CI_low > 0
  (NOT met — final verdict was INCONCLUSIVE_THIN_COVERAGE → practical KILL);
  pre-registered order budget and plan; measured cost < gross edge required.
- **Status:** PARKED. Preconditions currently fail — listed for honesty, not intent.

### Correlation-vs-book fit input (deferred from fit verdict, 2026-06-11)
- **Hypothesis:** none — this is descriptive arithmetic (pairwise return correlation
  of a candidate vs current holdings), not a predictive claim.
- **Why parked:** medium build cost vs weekend wrap deadline; needs price-history
  fan-out per holding.
- **Entry path:** ordinary feature work post-wrap (no pre-registration needed —
  descriptive), budgeted under the ~1 hr/quarter maintenance allowance.
