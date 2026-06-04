# ADR-034: Adaptive Intelligence — Pattern Memory and Weight Evolution

**Date:** 2026-06-03
**Status:** Accepted
**Deciders:** Tirth Joshi

## Context

Phases 7-8 introduced conviction scoring with static weights and outcome tracking. The system records which signals fire and what happens, but doesn't act on this knowledge. Weights remain at defaults regardless of observed performance.

## Decision

Add adaptive intelligence with three mechanisms:

1. **Pattern memory** — groups outcomes by signal combination, computes hit rate and avg return per pattern
2. **Weight adjustment** — automatically boosts weights for signals with >65% hit rate, reduces for <50%, with guardrails (max +/-0.2 per cycle, floor 0.05, ceiling 3.0)
3. **Rule discovery** — emerges "suppress" rules for reliably bad patterns and "boost" rules for reliably good ones, with confidence scoring

## Consequences

- Conviction weights evolve based on outcome data
- System gets smarter over time without manual tuning
- Weight history provides full audit trail on System Intelligence tab
- Learned rules are surfaced with confidence levels
- Human can always override — manual weight adjustment takes precedence
- Guardrails prevent wild swings (max 0.2 change per cycle)
