# ADR-024: Historical Sentiment via Google Trends + GDELT

**Date:** 2026-06-01
**Status:** Accepted
**Deciders:** Tirth Joshi

## Context

The RSS daily scan (ADR-022) builds sentiment history from the day it is first run. If the project starts today, meaningful sentiment data won't accumulate for weeks — blocking the core thesis (ADR-001) from being tested against historical price data.

The fundamental problem: backtesting requires sentiment signals at historical timestamps. Without historical sentiment, the backtest (run in Phase 3A) tested only technical features, not the combined thesis. Testing the actual hypothesis requires years of historical sentiment aligned with historical prices.

Two free sources cover this gap:
- **Google Trends** — normalized search volume for any query going back to 2004. Highly correlated with retail investor attention and buzz spikes.
- **GDELT** — Global Database of Events, Language, and Tone. 300+ million news articles globally, with tone scores, available for download via BigQuery or direct CSV. Covers 2015–present at daily granularity.

## Decision

Use **pytrends** (Google Trends unofficial API) for historical search volume as a proxy for retail buzz. Use **GDELT** for historical news sentiment via tone scores. Together these provide 5+ years of historical sentiment for backtest alignment.

Live pipeline continues to use the RSS + NewsAPI feed (ADR-022) for forward-looking signals. Historical sources are used only during backtest data preparation — they are not in the hot path.

Architecture:
- `adapters/data/google_trends_adapter.py` — implements `SentimentPort` for historical data. Wraps pytrends with rate-limit backoff (Trends blocks after ~10 req/hr).
- `adapters/data/gdelt_adapter.py` — implements `SentimentPort` for historical news tone. Downloads daily GDELT export CSVs, filters by ticker mention in article metadata.
- `application/use_cases/historical_sentiment_loader.py` — `HistoricalSentimentLoaderUseCase` orchestrates both adapters, aligns to ticker + date, writes to `historical_sentiment` SQLite table.
- Live pipeline (`WeeklyTournamentUseCase`) reads from `buzz_signals` (RSS-populated). Historical backtest reads from `historical_sentiment`. Same port, different adapter.

Google Trends caveat: relative search volume (0-100 normalized within the query), not absolute counts. Features derived from Trends must be z-scored per ticker to make them comparable across different tickers.

## Alternatives Considered

- **Wait for live RSS accumulation** — 3-6 months before enough signal exists for meaningful backtesting. Blocks the core thesis test entirely. Rejected.
- **NewsAPI historical tier** — free tier only covers the past month. Paid tier ($449/month) is out of budget for a portfolio project. Rejected.
- **Twitter/X Academic API** — was an excellent source but access requires approved academic application. No guarantee of approval. Rejected as primary source.
- **Alpha Vantage News Sentiment** — limited history on free tier (50 API calls/day). Rejected as primary; may revisit as a supplement.
- **Web-scraped historical headlines** — legal risk, rate-limit complexity, inconsistent coverage. Rejected.

## Consequences

**Positive:**
- Enables the actual combined thesis backtest from Phase 3A spec — technical + sentiment vs technical-only
- pytrends is free and covers 5+ years with daily granularity
- GDELT is free, comprehensive, and continuously updated
- Both sources store into `historical_sentiment` SQLite — same schema as `buzz_signals`, no new query patterns needed

**Negative:**
- pytrends is an unofficial API — can break without notice, has strict rate limits (~10 req/hr)
- GDELT CSV downloads are large (~100MB/month), requiring a one-time batch ingestion job
- Google Trends normalization (0-100 relative) makes cross-ticker comparisons unreliable without z-scoring — this must be enforced in the FundamentalFeatureEngineer or a dedicated normalization step
- GDELT tone scores are noisy — not trained on financial text. Flan-T5 (ADR-004) remains the production scorer; GDELT tone is a historical proxy, not a replacement

## Superseded By
None
