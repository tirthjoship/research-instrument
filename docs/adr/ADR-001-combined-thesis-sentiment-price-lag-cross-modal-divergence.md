# ADR-001: Combined thesis — sentiment-price lag + cross-modal divergence

**Date:** 2026-05-23
**Status:** Accepted
**Deciders:** Tirth Joshi

## Context
Needed a testable investment thesis. Considered sector rotation, earnings surprise, sentiment-price lag alone, and cross-modal divergence alone.

## Decision
Combined sentiment-price lag (A) with cross-modal divergence (B). A feeds into B naturally — you need lag measurement before you can detect divergence.

## Alternatives Considered
- **(C) Sector rotation** — harder to explain concisely, needs broad coverage.
- **(D) Earnings surprise** — quarterly only, needs expensive options data.
- **(A) or (B) alone** — combining gives one coherent story, not two projects.

## Consequences
**Positive:**
- Single coherent interview story.
- Contrarian signals are what hedge funds trade.
- If no signal found, negative result is still publishable.

**Negative:**
- More complex than single thesis.
- Requires both technical and sentiment data pipelines.

## Superseded By
None
