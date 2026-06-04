# ADR-035: Dashboard Redesign — WealthSimple-Inspired 5-Tab Layout

**Date:** 2026-06-03
**Status:** Accepted
**Deciders:** Tirth Joshi

## Context

The dashboard grew from 6 tabs across Phases 5-9 without unified design. Two recommendation systems (conviction + tournament) confused users. Layout was data-dense but not informative. Looked like a Streamlit prototype, not an investment tool.

## Decision

Complete redesign with WealthSimple-inspired aesthetic:

1. **5 tabs in 3 modes:** Act (Today's Opportunities, Watchlist), Track (My Portfolio), Understand (How It Works, Market Context)
2. **Killed tournament tab** — conviction engine is the sole recommendation source
3. **Signal Breakdown merged** into opportunity card expansion (not separate tab)
4. **Auto-scan with smart cache** — 15min market hours, 60min after hours
5. **3-panel hero** — Market Status (EST), Your Portfolio, Today's Signal
6. **Compact opportunity cards** — scannable with expandable signal detail
7. **Guided onboarding** — first-run 3-step card
8. **DM Sans + Inter + JetBrains Mono** — distinctive typography
9. **Collapsible sections** in How It Works with learning progress gamification
10. **Light theme, friendly voice** — conversational verdicts, plain English

## Consequences

- Simpler mental model (5 tabs vs 6, one recommendation system vs two)
- Auto-scan removes friction (no button click every visit)
- Onboarding guides new users
- Signal Breakdown preserved but accessed in context (per-card)
- Consistent ws-card styling across all tabs
