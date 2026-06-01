# ADR-023: Expanded Ticker Universe — S&P 500 + NASDAQ-100

**Date:** 2026-06-01
**Status:** Accepted
**Deciders:** Tirth Joshi

## Context

Phase 3A used 40 hardcoded S&P 500 mega-caps as the ticker universe. This was sufficient for proving out the technical feature pipeline but is too narrow for the sentiment-driven discovery thesis (ADR-002). The RSS daily scan (ADR-022) regularly surfaces tickers like AMD, PLTR, SMCI, and RIVN that fall outside the top-40 — but without pre-trained technical history cached via ADR-017, those tickers produce cold-start failures during weekly tournament.

The gap: buzz-discovered tickers need technical history to be ranked. If the universe is too small, sentiment discovery is decorative — it finds signals that can't be acted on.

## Decision

Expand the ticker universe to the full S&P 500 + NASDAQ-100 intersection (~350 unique tickers after deduplication). All tickers are pre-trained upfront using the ADR-017 caching strategy so technical history is available before the weekly tournament runs.

Universe management is config-driven:
- `config/tickers/sp500.txt` — S&P 500 constituents (one ticker per line)
- `config/tickers/nasdaq100.txt` — NASDAQ-100 constituents
- `config/tickers/excluded.txt` — manual exclusions (ADRs, ETFs, recently listed with < 2 years history)
- Union of sp500 + nasdaq100 minus excluded = active universe loaded at startup

Pre-training re-runs weekly (Saturday) to catch index reconstitutions. ADR-017 cache prevents re-fetching unchanged data.

## Alternatives Considered

- **Tiered universe (top 100 full, rest on-demand)** — on-demand pre-training during a live tournament run would add unpredictable latency and yfinance rate-limit risk. Rejected.
- **Sector sampling (~150 tickers)** — cleaner compute budget, but misses key tickers that don't appear in curated sector baskets (PLTR, CRWD, etc.). Rejected.
- **Full Russell 1000** — ~1,000 tickers. Pre-training cost too high on M2 MacBook Air. yfinance rate limits become a wall. Revisit in Phase 5 with async batching. Rejected for now.
- **Dynamic universe only (no static list)** — pure buzz-driven with no pre-training. Cold-start problem remains unsolved. Rejected.

## Consequences

**Positive:**
- RSS-discovered tickers almost always fall within S&P 500 + NASDAQ-100, eliminating cold-start failures
- Config-driven files make index reconstitution updates a one-line diff, not a code change
- Pre-training once weekly amortizes yfinance cost across the full universe upfront

**Negative:**
- Pre-training wall-clock time increases from ~25 min (40 tickers) to ~3 hours (350 tickers) on first run — acceptable as a one-time cost with ADR-017 caching cutting subsequent runs to minutes
- Excluded list requires periodic human review as new tickers join indices
- Universe files must be kept in sync with actual index constituents — a maintenance burden

## Superseded By
None
