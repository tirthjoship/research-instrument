# ADR-036: Phase 5.4 — SimplyWallSt-Grade Dashboard Redesign

**Date:** 2026-06-04
**Status:** Accepted
**Deciders:** Tirth Joshi

## Context

Dashboard shipped in Phases 5.0-5.3 has 838 tests and hexagonal architecture but doesn't reflect the project's depth. Conviction engine only uses 1 of 6 signal dimensions (3 hardcoded placeholders). Only 2 of 350 tickers appear. No charts on most tabs. Rich data (15 recommendations, 193 buzz signals, 133 evaluation runs, yfinance fundamentals) sits unused in SQLite.

SimplyWallSt was identified as the visual benchmark. Their product is a visualization layer on financial APIs. Our project has MORE data (5 ML signal layers + sentiment + conviction + adaptive learning) but worse presentation.

## Decision

Redesign the entire dashboard to match SimplyWallSt visual quality while surfacing our unique ML intelligence layer. Approach B: SimplyWallSt-grade redesign within Streamlit framework.

Key changes:
1. **Fix conviction engine** — wire 3 placeholder sub-scores to real data (buzz_signals, yfinance fundamentals, stored recommendations)
2. **Adopt SWST design language** — every section: criteria card (score N/M with dots) → plain English → chart → verdict bullets (✅/⚠️/❌)
3. **New Stock Analysis tab** — full 7-section deep dive for any ticker, matching SWST's section structure plus our unique signal radar
4. **Charts everywhere** — ~20-25 Plotly charts across all tabs (radar, gauge, treemap, candlestick, timeline, comparison bars)
5. **Live prices** — batch yfinance fetch with 5-min cache for all displayed tickers
6. **Progressive loading** — Google-style step messages for every operation >2 seconds

## Alternatives Considered

- **A: Fix What's Broken** — minimal fixes, add a few charts. Rejected: still looks like data engineering demo.
- **C: React/Next.js rewrite** — maximum visual control. Rejected: massive scope, loses hexagonal benefits, new testing framework.

## Consequences

- 6 implementation phases, ~52 tasks
- ~50-80 new tests (target 890+ total)
- New files: price_cache.py, cards.py, stock_analysis.py, stock_analyzer.py
- Conviction engine gets real sub-scores (backward compatible: None → fallback to current behavior)
- All 838 existing tests must continue passing
- Signal Radar (6-axis) becomes our visual signature, equivalent to SWST's Snowflake

## References

- Design spec: `docs/superpowers/specs/2026-06-04-phase-54-dashboard-redesign.md`
- Reference notes: `docs/design-references/REFERENCE_NOTES.md`
- SimplyWallSt screenshots analyzed: 28 (temporary files, patterns documented)
