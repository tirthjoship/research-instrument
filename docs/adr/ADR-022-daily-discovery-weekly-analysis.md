# ADR-022: Daily Discovery Scan + Weekly Full Analysis

**Date:** 2026-05-30
**Status:** Accepted
**Deciders:** Tirth Joshi

## Context

Phase 3A uses a static 40-ticker universe (hardcoded S&P 500 mega-caps). The project thesis (ADR-001) requires dynamic buzz-driven discovery (ADR-002) to find emerging opportunities before price moves. The core hypothesis — sentiment leads price by 1-48 hours — means a weekly-only scan may miss the window entirely.

However, full ML analysis (feature engineering + ensemble prediction + Stage 2 stacking) is too expensive to run daily on an M2 MacBook Air, especially with yfinance rate limits causing 25+ minute hangs on 40 tickers.

## Decision

Two-cadence architecture:

### Daily Scan (lightweight, ~2.5 minutes)

**What:** Scan RSS feeds from 6 publishers. Extract ticker mentions. Score each article with both KeywordScorer (instant) and FlanT5Scorer (~0.3s/article on MPS). Store all signals in `buzz_signals` SQLite table.

**Triggered by:** `python -m application.cli daily-scan`

**Output:** `buzz_signals` table rows with columns:
```sql
buzz_signals (
    id INTEGER PRIMARY KEY,
    ticker TEXT NOT NULL,
    source TEXT NOT NULL,
    mention_count INTEGER NOT NULL,
    sentiment_raw REAL NOT NULL,
    scorer TEXT NOT NULL,          -- 'keyword', 'flan_t5', 'rss_raw'
    fetched_at TIMESTAMP NOT NULL,
    article_hash TEXT NOT NULL UNIQUE  -- dedup
)
```

**Ticker discovery:** Tickers extracted from article text via regex + known S&P 500 ticker validation. No fixed universe — any mentioned ticker gets tracked.

### Weekly Analysis (full compute, 10-30 minutes)

**What:** Read accumulated `buzz_signals` from past 7 days. Rank tickers by **buzz acceleration** (week-over-week mention change, not absolute volume). Filter by `us.yaml` quality gates (min market cap, min volume, no penny stocks). Run Stage 1 (frozen technical) + Stage 2 (sentiment blend) on qualifying tickers. Output Top 15 picks.

**Triggered by:** `python -m application.cli run-tournament`

**Key insight:** Buzz **acceleration** drives discovery, not absolute volume. A stock going from 5 to 50 mentions (10x) is more interesting than one steady at 500. This catches waves early.

### Why Two Cadences

| Concern | Daily-only | Weekly-only | Dual (chosen) |
|---------|-----------|-------------|---------------|
| Catches emerging tickers | Yes | Too late | Yes (daily discovery) |
| Full ML analysis | Too expensive | Yes | Yes (weekly analysis) |
| yfinance rate limits | Painful (40 tickers daily) | Manageable | Avoided (daily = RSS only, no yfinance) |
| Flan-T5 compute | ~2.5 min acceptable | N/A | Daily only |
| Data accumulation | Good | Sparse | Good (7 days of signals for weekly) |

## Automation

Phase 3B: **CLI-only** (manual invocation). Automation deferred to Phase 4 (ADR-007).

Future (Phase 4):
- Daily scan → `launchd` plist (local cron) — needs MPS for Flan-T5
- Weekly analysis → GitHub Actions scheduled workflow — reads pre-computed buzz_signals from SQLite

## Alternatives Considered

- **Daily full analysis** — too expensive, yfinance rate limits. Rejected.
- **Weekly-only scanning** — misses 1-48 hour sentiment-price lag window. Rejected.
- **Hourly scanning** — overkill for RSS feeds that update 2-4x/day. Rejected.
- **GitHub Actions for daily scan** — can't use MPS (GitHub runners are x86 Linux). Rejected for Phase 3B.

## Consequences

**Positive:**
- Catches emerging tickers before weekly tournament — can "ride the wave"
- Daily signals accumulate for richer weekly analysis (7 days of sentiment history)
- Lightweight — daily scan doesn't touch yfinance, only RSS feeds
- Buzz acceleration surfaces stocks where buzz is **growing**, not just high

**Negative:**
- Two CLI commands instead of one — user must remember to run both
- Daily scan without weekly analysis produces raw data but no recommendations
- Accepted: Phase 4 automation eliminates manual burden

## Superseded By
None
