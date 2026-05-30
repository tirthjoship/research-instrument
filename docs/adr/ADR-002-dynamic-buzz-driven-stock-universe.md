# ADR-002: Dynamic buzz-driven stock universe over fixed index

**Date:** 2026-05-23
**Status:** Accepted
**Deciders:** Tirth Joshi

## Context
Needed to decide which stocks to analyze each week. Options included S&P 500, sector-focused, personal watchlist, mid-cap momentum, or dynamic discovery.

## Decision
Dynamic universe — let weekly buzz across news/social/analyst sources define the candidate pool (~50-100 raw, filtered to 30-50 qualified). No pre-defined list.

## Alternatives Considered
- **S&P 500** — efficient market makes alpha hard.
- **Sector-focused** — limits generalizability.
- **Personal watchlist** — too small, overfitting risk.

## Consequences
**Positive:**
- Avoids selection bias.
- Surfaces high-attention stocks where sentiment matters most.
- More realistic (professional quant funds screen dynamically).

**Negative:**
- Survivorship bias risk — misses quiet movers.
- Data quality varies for obscure stocks.
- Mitigated by minimum 3 mentions + volume/price filters.

## Superseded By
None
