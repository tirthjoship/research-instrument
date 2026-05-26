# ADR-017: Raw data caching at fetch time for reproducibility

**Date:** 2026-05-25
**Status:** Accepted
**Deciders:** Tirth Joshi

## Context
Pipeline depends on external APIs (yfinance, Reddit, RSS, StockTwits, Google CSE) that return different data on every call. Prices get adjusted retroactively, posts get deleted/edited, feeds rotate articles, search results vary by time. Running the same pipeline twice on the same prediction date produces different features, different predictions, different picks.

This breaks: reproducibility, debugging, auditing, and makes walk-forward validation non-deterministic.

## Decision
Every adapter caches its raw API response at fetch time before processing. Cache is keyed by `(source, ticker_or_query, fetch_timestamp)`.

### Cache structure
```
data/cache/
  yfinance/{symbol}/{YYYY-MM-DDTHH:MM:SS}.parquet
  reddit/{subreddit}/{YYYY-MM-DDTHH:MM:SS}.json
  rss/{feed_name}/{YYYY-MM-DDTHH:MM:SS}.json
  stocktwits/{symbol}/{YYYY-MM-DDTHH:MM:SS}.json
  google_cse/{query_hash}/{YYYY-MM-DDTHH:MM:SS}.json
```

### Adapter behavior
```python
class CachingAdapter:
    def __init__(self, cache_dir: Path, use_cache: bool = False):
        self._cache_dir = cache_dir
        self._use_cache = use_cache

    def fetch(self, key, fetch_fn):
        if self._use_cache:
            return self._load_cached(key)
        data = fetch_fn()
        self._save_cache(key, data)
        return data
```

- `use_cache=False` (default, live mode): fetch from API, save to cache
- `use_cache=True` (replay mode): load from cache, never hit API

### Implementation
- Base `CachingMixin` class that all adapters inherit
- Cache dir configurable, defaults to `data/cache/`
- `.gitignore` the cache directory (raw data, not committed)
- Cache files are append-only (never overwrite past fetches)

### Storage estimate
~50MB/week across all sources. ~2.5GB/year. Trivial for local disk.

## Alternatives Considered
- **No caching** — non-reproducible pipeline. Can't debug, audit, or replay. Rejected.
- **Database caching (SQLite/Postgres)** — overengineered for raw response storage. Rejected for Phase 3, reconsider if query patterns emerge.
- **Cache only yfinance** — other sources equally non-deterministic. Rejected.

## Consequences
**Positive:**
- Any past run is exactly reproducible via replay mode.
- Debugging: inspect raw data that produced a bad prediction.
- Cached data becomes sentiment backfill dataset over time (12+ weeks of cache = robust backfill).
- Walk-forward validation is deterministic when run from cache.
- Audit trail: every data point traceable to source and fetch time.

**Negative:**
- Disk space (~2.5GB/year). Trivial.
- Adds ~2-3 hours implementation across all adapters.
- Cache can become stale if relied on accidentally in live mode.
- Mitigated: `use_cache` flag is explicit, never implicit.

## Superseded By
None
