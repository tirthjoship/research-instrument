# ADR-032: Opportunity Intelligence Engine

**Date:** 2026-06-03
**Status:** Accepted
**Deciders:** Tirth Joshi

## Context

The existing ML-based direction predictor achieved 46-49% accuracy on a full S&P 500 + NASDAQ backtest — no statistical edge. Technical indicators on mega-cap stocks are well-arbitraged. The system needs a fundamentally different approach to deliver value.

## Decision

Reframe from direction prediction to opportunity surfacing with conviction scoring:

1. **Multi-signal conviction engine** — weighted scoring across 6 dimensions (signal agreement, smart money, sentiment, fundamentals, freshness, ML direction)
2. **SEC EDGAR integration** — 13D activist filings and Form 4 insider trades as "smart money" signals
3. **4-part opportunity cards** — Alert, Evidence, Suggestion, Risk in beginner-friendly language
4. **Hybrid universe** — scan 350+ tickers, surface top 15, pin watchlist favorites
5. **Existing ML kept** — low-weight (0.3) input to conviction scoring, value determined by future outcome tracking

## Consequences

- Direction prediction becomes one input signal, not the system's purpose
- Dashboard evolves: Command Center → Opportunity Feed
- Future phases add outcome tracking (Phase 8) and adaptive learning (Phase 9)
- The "honest data scientist" narrative strengthens — acknowledging limitations and reframing around genuine value
- SEC EDGAR adapter adds 2 new free data sources with no API key required
