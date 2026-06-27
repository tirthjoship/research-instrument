# ADR-063: SP3 Screener Blend Formula — Equal-Weight Factor + Convergence Tier

**Status:** Accepted (retroactive)
**Date:** 2026-06-23
**Related:** ADR-062 (corroboration engine pivot), ADR-049 (RESEARCH_ONLY gate)

## Context

SP3 adds a corroboration overlay to the factor screener. Two signals now rank each ticker:

1. **Factor percentile** — composite z-score rank across momentum, revision, quality, volatility (existing `EvidenceScreenUseCase`)
2. **Convergence tier** — STRONG/MODERATE/WEAK/CONFLICTED/NONE from `CorroborationStore`

A blending formula is needed to produce a single `blended_percentile` sort key for `ScreenedRow`. The formula must be transparent (user sees both components), not claim predictive validity (ADR-049: RESEARCH_ONLY), and be simple enough to explain in one sentence.

## Decision

**Equal-weight rank-average: `blended_percentile = 0.5 * factor_pct + 0.5 * tier_pct`**

Tier → numeric rank:
- STRONG: 1.0
- MODERATE: 0.67
- WEAK: 0.33
- CONFLICTED: 0.0
- NONE / no snapshot: factor-only (tier not applied)

When no corroboration snapshot exists within the staleness window (7 days), `factor_only=True` and the ticker ranks on factor percentile alone — clearly labelled in CLI output.

## Alternatives Rejected

**IC-optimised weights** — requires historical resolution data to compute. No such data exists yet (SP5 forward gate is still accruing). Using IC-optimised weights before validation would be p-hacking.

**Factor-only** — loses the corroboration signal entirely; defeats the purpose of SP3.

**Tier-only** — discards factor quality entirely; a STRONG-tier ticker with terrible fundamentals would rank above a WEAK-tier ticker with strong fundamentals.

**Conviction-weighted** — `reliability_weight` per source varies but is currently static (not proven). Using unvalidated weights as ranking inputs overstates certainty. Deferred to post-SP5.

## Consequences

- All screener output clearly shows both `factor_percentile` and `convergence_tier` alongside `blended_percentile` so users can see the basis.
- Equal-weight is a conservative, defensible choice: it makes no claim about which signal is more predictive.
- When SP5 validates (or kills) the corroboration signal, the blend weight can be updated with IC evidence — at that point an ADR amendment is required.
- Tickers with no corroboration snapshot are not penalised — they rank on factor alone, labelled `factor_only=True`.
