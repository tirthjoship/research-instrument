# Spec Brief — SP3: Screener Revamp (Corroboration consumer)

**Status:** Design brief (needs its own brainstorm → full spec → plan before coding)
**Depends on:** SP1 Corroboration Engine; existing `EvidenceScreenUseCase`
**Date:** 2026-06-20

## Purpose
The screener "feels random" — it ranks the static universe on factor IC alone (INCONCLUSIVE, IC=0.011,
ships RESEARCH_ONLY per ADR-049). Add a corroboration layer so every pick carries **basis + certainty**:
who-agrees (attributed) + our-factor-readout + convergence tier.

## Scope (in)
- Augment each screener row with its `CorroboratedCandidate` (if one exists for that ticker that week).
- New ranking = factor rank blended with convergence tier (transparent, weights shown), NOT a new
  prediction. Still RESEARCH_ONLY until SP5 validates.
- Surface "why this rank" = factor percentile + N verified sources + tier, per row.

## Scope (out)
- No promotion to "validated buy" — gated by SP5/ADR-049.
- No change to the factor screen math itself (reuse `EvidenceScreenUseCase`).

## Proposed approach
A `ScreenerCompositeService` (domain, pure) that joins `EvidenceScreen` output with the corroboration
snapshot by ticker and produces a `ScreenedRow` carrying both signals + a combined sort key. Show the
combined key's components so the user sees the basis (his "certainty" ask = legible evidence, not a
confidence number).

## Files likely touched
`domain/screener_composite_service.py` (new), `application/cli/screen_commands.py` (modify),
`application/screen_backtest_use_case.py` (read-only reuse), dashboard screener tab later (SP6).

## Open questions
- Blend weighting factor-vs-corroboration (default: rank-average, both shown; no hidden weight).
- What to show when a screened ticker has NO corroboration that week (default: factor-only, labelled).
- Keep the pre-registered IC gate (ADR-049) authoritative — corroboration does not bypass it.
