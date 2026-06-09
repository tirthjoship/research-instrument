# ADR-051: Calibration-Readiness — Date-Diversity Precondition for the ADR-048 Gate

**Date:** 2026-06-09
**Status:** Accepted
**Amends (design only, thresholds unchanged):** ADR-048
**Builds on:** ADR-047, ADR-050 (discipline is the terminal bet)

## Context

The ADR-048 discipline REDUCE-flag forward gate is the project's terminal bet. On
2026-06-09 its forward log held 132 rows ALL dated 2026-06-08 (46 REDUCE). Two flaws
threatened it: (1) no automated logging — the documented launchd plist runs
`daily-cycle` (opportunity loop), which never appends discipline verdicts; (2) a
single-`as_of` confound — all REDUCE flags would resolve over one identical market
window, so the pooled down-rate would ride on that one month's direction, not on
whether the flags discriminate. A confounded PROCEED and a confounded KILL are
equally worthless.

## Decision

Strengthen the EXPERIMENTAL DESIGN before any outcome is observable (earliest flag
resolves ~2026-06-30; this is decided 2026-06-09). The ADR-048 thresholds are
UNCHANGED: down_rate >= 0.55 AND brier <= 0.45 AND n >= 30, 21-day horizon.

Add a pre-resolution **date-diversity precondition**, pre-committed here:
- The resolved REDUCE sample must span **>= 3 distinct as_of dates over >= 10
  calendar days** before the locked thresholds are evaluated.
- Below that → **INCONCLUSIVE_THIN_DATES** (an honest design failure: we did not
  collect a clean sample), never PROCEED and never KILL.

Implemented as: daily `holdings-risk` logging (cron), a `discipline-calibration-status`
readiness view, and a symmetric `diversity_label` guard wired into
`resolve-discipline-flags`.

### Anti-p-hacking protections (pre-committed)

1. **Symmetric:** the guard blocks a confounded PROCEED and a confounded KILL alike.
2. **Fixed thresholds:** k=3 dates, d=10 days set now, not tuned to observed down-rates.
3. **Fixed resolution date:** the gate resolves in the ADR-048 mid-late-July window;
   we do NOT extend collection to chase a result. Whatever diverse sample exists then
   is the sample. INCONCLUSIVE_THIN_DATES at that date is a permitted terminal outcome.

## Consequences

- The gate can only return PROCEED/KILL on a non-confounded sample — the result, either
  way, becomes trustworthy.
- If diversity is still insufficient at the resolution date, the honest outcome is
  INCONCLUSIVE_THIN_DATES, and the discipline tool ships as decision-support without a
  validated forward edge (consistent with the ADR-050 terminal-state framing).
- No domain change; no scorer change; no threshold change.
