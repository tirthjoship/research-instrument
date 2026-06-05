# ADR-037: Phase 5.5 — Investment Intelligence UX Overhaul

**Date:** 2026-06-04
**Status:** Accepted
**Deciders:** Tirth Joshi

## Context

Phase 5.4 built infrastructure (15+ chart builders, conviction engine fix, Stock Analysis tab, 996 tests) but visual QA revealed the dashboard still shows data without recommending actions. Tabs are too many (6), sections are redundant, watchlist is passive, portfolio has no benchmark, and empty states look abandoned.

Research into Portfolio Genius, PortfolioPilot, SimplyWallSt, and Wealthsimple revealed that best-in-class investment dashboards provide: action queues, portfolio health scores, benchmark comparison, diversification analysis, AI-generated summaries, and smart alerts.

## Decision

1. **Restructure to 5 tabs:** Dashboard (action queue), Opportunities (merged watchlist + conviction), My Portfolio (table + benchmark + AI summary), Stock Analysis (+ Gemini AI), System Intelligence (merged How It Works + Market Context).

2. **Action-oriented design:** Every element answers "what should I do?" with green/amber/red action sentences.

3. **Portfolio intelligence:** Health score (0-10), portfolio vs SPY benchmark chart, sector allocation pie, diversification warnings.

4. **Smart watchlist:** System generates insights per ticker instead of user typing notes. Shows speculation horizon and entry signals.

5. **Gemini free tier integration:** AI Deep Analysis on Stock Analysis tab + AI Portfolio Summary on Portfolio tab. Zero cost. Clearly labeled as AI-generated.

6. **Domain-layer insight generation:** Pure functions `generate_card_insight()` and `compute_portfolio_health()` in domain layer — testable, no I/O.

## Alternatives Considered

- LLM-generated insights everywhere (rejected: non-reproducible, rate-limited, hard to test)
- Keep 6-tab structure (rejected: too much navigation, content scattered)
- Paid data sources (rejected: user constraint — zero cost)

## Consequences

- 7 implementation phases (A-G), ~32 tasks
- 3 new domain files (insight_service.py, portfolio_service.py, gemini_insight.py)
- 3 old tab files deleted, 3 new tab files created
- Gemini free tier dependency (optional, graceful fallback)
- All existing 996 tests preserved + ~50-80 new tests

## References

- Spec: `docs/superpowers/specs/2026-06-04-phase-55-ux-overhaul.md`
- Phase 5.4 QA feedback: saved to memory
- Research: Portfolio Genius, PortfolioPilot, SimplyWallSt, Wealthsimple (2026)
