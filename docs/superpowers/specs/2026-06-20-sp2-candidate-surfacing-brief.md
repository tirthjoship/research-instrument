# Spec Brief — SP2: Candidate Surfacing (Corroboration consumer)

**Status:** Design brief (needs its own brainstorm → full spec → plan before coding)
**Depends on:** SP1 Corroboration Engine (`CorroboratedCandidate`, `CorroborationStore`)
**Date:** 2026-06-20

## Purpose
Let genuinely NEW tickers (not in `sp500.txt`/`nasdaq100.txt`/`themes.yaml`) enter the system when
credible sources corroborate them. Today the universe is frozen; `scan-opportunities` only admits
tickers already in the static `_KNOWN_TICKERS` (~120) set (see research doc §c/§d).

## Scope (in)
- A `SurfacingUseCase` that takes the weekly `CorroboratedCandidate` list and admits new tickers whose
  `convergence ∈ {STRONG, MODERATE}` AND `verification == ALL_VERIFIED` into a discovered-universe overlay.
- Persist discovered tickers (extend `CorroborationStore` or reuse `surfaced_calls`) with the corroboration
  evidence attached, so they forward-resolve under SP5.
- Resolve new ticker → company name / sector (yfinance `info`) for downstream readouts.

## Scope (out)
- No buy language. Surfacing = "credible sources flag this + our readout" — RESEARCH_ONLY.
- No change to existing screen/scan universes (SP3 handles screener).

## Proposed approach
Extend `HybridUniverseProvider` (`adapters/data/hybrid_universe_provider.py`) with a third source:
`corroboration_overlay` = STRONG/MODERATE corroborated tickers from the latest snapshot. Cap admissions
(default 10/week) to control free-tier verification cost. Reuse `source_reliability` weighting.

## Files likely touched
`application/surfacing_use_case.py` (new), `adapters/data/hybrid_universe_provider.py` (modify),
`application/cli/scan_commands.py` (wire), `domain/` (a `DiscoveredTicker` type if needed).

## Open questions
- Admission threshold: STRONG-only or STRONG+MODERATE? (default STRONG+MODERATE, capped 10/wk)
- De-dup vs existing universe + watchlist; never auto-add to portfolio.
- How long a discovered ticker persists if corroboration decays (default: drop after 2 dry weeks).
