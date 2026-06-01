# ADR-026: Portfolio Holdings in SQLite with Sell Signal Detection

**Date:** 2026-06-01
**Status:** Accepted
**Deciders:** Tirth Joshi

## Context

The current system generates weekly buy recommendations (Top 15 picks, graded Strong Buy through Hold). It has no concept of what the user currently owns, which means it cannot generate sell signals. A recommendation engine without sell logic is incomplete — knowing when to exit a position is as important as knowing when to enter.

The 5-tier grading system (ADR-001) already defines "May Sell" and "Immediate Sell" grades, but these are computed relative to the ranked list. Without knowing which tickers the user holds, the system cannot flag "you own NVDA and here is a sell signal specific to your holding."

The sell signal problem requires tracking state: entry price, entry date, current unrealized P&L, and the sentiment/technical trend at time of entry vs now.

## Decision

Store portfolio holdings in a new `holdings` SQLite table (same database as existing `recommendations` and `buzz_signals` tables). Manual entry via CLI. No brokerage API integration in this phase.

Schema:
```sql
holdings (
    id INTEGER PRIMARY KEY,
    ticker TEXT NOT NULL,
    shares REAL NOT NULL,
    entry_price REAL NOT NULL,
    entry_date DATE NOT NULL,
    stop_loss_price REAL,           -- optional, user-set
    notes TEXT,
    created_at TIMESTAMP NOT NULL,
    updated_at TIMESTAMP NOT NULL
)
```

CLI commands:
- `python -m application.cli add-holding NVDA 10 --entry-price 875.00 --entry-date 2026-04-15`
- `python -m application.cli remove-holding NVDA`
- `python -m application.cli show-holdings`

`MonitorHoldingsUseCase` runs at the end of each weekly tournament and checks each held ticker against four sell triggers:

1. **Negative sentiment flip** — sentiment score was positive at entry, now negative for 3+ consecutive days
2. **Technical breakdown** — price closes below 20-day SMA and RSI < 40 simultaneously
3. **Stop-loss breach** — current price <= user-set stop_loss_price
4. **Cross-asset contagion** — a ticker in the same supply chain / correlation cluster (ADR-027) has already broken down, and this ticker shows early weakness

Sell signal severity:
- Any 1 trigger → "May Sell" flag
- Any 2+ triggers → "Immediate Sell" alert

Output stored in `sell_signals` SQLite table and surfaced in the weekly report.

## Alternatives Considered

- **Brokerage API integration (Questrade, IBKR)** — real-time sync of actual positions. Architecturally correct long-term. Too complex for current phase: OAuth flows, rate limits, brokerage-specific schemas, paper trading vs live account risk. Deferred to Phase 5/6. Rejected now.
- **CSV import** — considered as a supplement for bulk entry (import from brokerage export). Will be added as a convenience feature on top of the SQLite model, not a replacement.
- **In-memory state only** — holdings disappear on restart. Useless for a weekly-cadence tool. Rejected.
- **External portfolio tracker API (Sharesight, etc.)** — adds third-party dependency and cost. Rejected.

## Consequences

**Positive:**
- Completes the full buy-hold-sell loop the project thesis requires
- SQLite is already the persistence layer — no new infrastructure
- Manual CLI entry is frictionless for a personal portfolio tool
- Stop-loss tracking prevents the system from generating silent holds on losing positions
- Cross-asset contagion sell signals (from ADR-027 graph) create a unique differentiated signal not available in standard recommendation tools

**Negative:**
- Manual entry means holdings can drift out of sync with reality (user buys/sells without updating CLI)
- No real-time price feed — sell signals are computed weekly, not intraday. A stock could gap down 20% before the next weekly run catches it
- Stop-loss monitoring is passive (weekly check), not active (live price alert). Deferred to Phase 5 with a lightweight daily price-check cron

## Superseded By
None
