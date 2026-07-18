# ADR-065: FMP Peers as a Cross-Market Supply-Chain Candidate Source

**Date:** 2026-07-17
**Status:** Accepted
**Deciders:** Tirth Joshi

## Context

ADR-027's hybrid supply-chain resolver (`adapters/visualization/analysis/supply_chain_resolver.py`)
scores two candidate sources per ticker — every YAML group it appears in
(`config/relationships/supply_chain.yaml`) and a curated industry/sector peer
pool (`loaders.INDUSTRY_PEERS` / `SECTOR_PEERS`) — against measured co-movement,
picking whichever clears `MIN_MEMBERS` (4) and `MIN_COMOVEMENT` (0.4).

Both sources are US-only. Every Canada/India ticker gets zero candidates and an
unconditional DATA-GAP, regardless of whether a real supply-chain relationship
exists. Confirmed live: `FORCEMOT.NS` (Force Motors, a real NSE-listed auto-parts
maker with genuine news coverage) showed total supply-chain DATA-GAP purely
because neither US-only source has anything for it.

## Decision

Add Financial Modeling Prep's `stable/stock-peers` endpoint (`FMPAdapter.get_stock_peers`)
as a third candidate source, scored identically to the existing two — no
special-casing in `select_best_group`'s scoring loop.

Live-verified for all 3 markets this project covers before building anything:

| Market | Verified with | Result |
|---|---|---|
| US | `AAPL` | Real peers (`GOOGL`, `META`, `MSFT`, `NVDA`, ...) |
| Canada | `RY.TO` | Real peers, already `.TO`-suffixed (`BMO.TO`, `BNS.TO`, ...) |
| India | `FORCEMOT.NS` | Real peers, already `.NS`/`.BO`-suffixed |

No translation layer needed — FMP returns tickers already in the exact suffix
format yfinance expects for each market.

Peers are cached in a new `supply_chain_peers_cache` SQLite table (24h TTL,
mirrors the `buzz_signals` mixin's shape) so repeat dashboard page loads don't
re-hit the API. A live-fetch failure and a genuine "this ticker has zero FMP
peers" result are indistinguishable (`[]`), and neither is ever persisted —
mirrors PR #148's `_no_stale_empty` fix for a different cache, extended here as
a write-time rule instead of a read-time retry: an empty result is never
cache-worthy, so both cases simply retry live on the next call rather than
risk a transient failure being mistaken for a permanent answer.

## A bug this decision surfaced (fixed in the same window)

Wiring in a third, cross-market candidate source exposed a latent bug in the
*existing* US-only sector-pool source: `_industry_sector_pool` matched on
yfinance's generic sector/industry labels (`"Consumer Cyclical"`,
`"Technology"`, ...) with no market check. Since these labels are shared
across markets, a non-US ticker whose sector happened to match could get
American mega-caps offered as a candidate purely because the label matched —
confirmed live: `FORCEMOT.NS`'s sector (`"Consumer Cyclical"`) maps to
`SECTOR_PEERS["Consumer Cyclical"] = [AMZN, TSLA, HD, NKE]`, and that
candidate's co-movement reached 0.20 (didn't clear the 0.4 bar this time, but
could for another international ticker). This was invisible before this ADR's
change because the sector-pool source only ever competed against other
US-only candidates for US tickers. Fixed by gating `_industry_sector_pool` to
tickers with no non-US suffix (`.TO`, `.NE`, `.NS`, `.BO`) — FMP peers already
cover non-US markets correctly as a separate source.

## Alternatives Considered

- **Hand-curate Canada/India entries into `supply_chain.yaml`** — the original
  plan before this session's API research. Rejected: hand-typing tickers
  already produced one wrong entry (`TATAMOTORS.NS`, delisted post-demerger;
  real symbol is `TMPV.NS`) — exactly the failure mode a structured API call
  avoids, and it doesn't scale past a handful of manually-reviewed names.
- **Finnhub `/stock/peers`** — also returns real Canada peers, but `403
  Forbidden` for India (premium-gated on the free tier, confirmed via a real
  call). Rejected as the primary source since it doesn't cover all 3 markets;
  may still be reused for the separate Canada analyst-consensus fast-follow
  (STATUS.md NEXT ACTIONS #2), a different data shape entirely.
- **Scraping Screener.in for India-specific peer groupings** — `robots.txt`
  permits it, but the Terms of Service has an ambiguous "no public display of
  materials" clause a public Cloud dashboard could plausibly violate.
  Rejected once FMP proved sufficient without that risk — keeps ADR-062's "no
  scraping that violates ToS" principle intact rather than weakening it.

## Consequences

**Positive:**
- Canada and India tickers can now get a real, correlation-confirmed
  supply-chain group instead of an unconditional DATA-GAP — matching the
  quality bar US tickers have always had, not a lowered one (same
  `MIN_MEMBERS`/`MIN_COMOVEMENT` thresholds apply).
- Surfaced and fixed a real bug in the pre-existing US sector-pool source
  that had been latent (never exercised for non-US tickers) since ADR-027.

**Negative:**
- New external dependency (`FINANCIAL_MODELING_PREP_API_KEY`) — a missing or
  invalid key degrades to an empty candidate (honest gap, per `FMPAdapter`
  never raising), not a crash, but does need adding to Streamlit Cloud's app
  secrets as a manual post-merge step, same as `GEMINI_API_KEY` before it.
- A ticker's FMP-suggested peers are similarity-by-sector/market-cap, not
  guaranteed tight correlation — some tickers will still land on DATA-GAP if
  their real peers don't move together tightly enough (`FORCEMOT.NS` itself
  is one such case, confirmed live: co-movement 0.076 against its own FMP
  peers). This is the resolver working correctly, not a shortfall of this
  decision — a low-correlation "group" would be actively misleading to show.

## Confirmed unsolved by three independent providers (not this ADR's scope)

India's analyst-consensus gap (real human brokerage ratings/target prices)
was separately investigated this session and has no free-tier solution
anywhere: Finnhub (`403`), Alpha Vantage (two ticker formats tried, zero
results even for `RELIANCE`), FMP (`402 Payment Required` for India,
`200` for US). This is a confirmed, honest DATA-GAP matching the project's
"never fake data" philosophy — not something this ADR's peers work touches,
and not to be re-litigated without a paid-tier decision.
