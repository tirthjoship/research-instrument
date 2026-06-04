# ADR-033: Outcome Tracking and Signal Learning

**Date:** 2026-06-03
**Status:** Accepted
**Deciders:** Tirth Joshi

## Context

Phase 7 introduced conviction-based opportunity surfacing with static default weights. The system has no way to learn which signals actually lead to profitable outcomes. Users need to track trades and see which signals work for their investment style.

## Decision

Add outcome tracking with three components:

1. **Trade logging** — manual buy/sell recording linked to opportunity cards and the signals that fired
2. **Signal report card** — per-signal hit rate, average return, and actionable recommendations
3. **Historical bootstrap** — simulate past outcomes using historical price data for day-one intelligence

## Consequences

- Users see which signals work (hit rate, avg return per signal)
- Report card provides actionable guidance ("reduce ml_direction weight")
- Bootstrap prevents cold-start problem — system has data from day one
- Dashboard evolves: Positions → Outcome Tracker, Model Confidence → System Intelligence
- Phase 9 (adaptive learning) builds on this outcome data for automatic weight adjustment
