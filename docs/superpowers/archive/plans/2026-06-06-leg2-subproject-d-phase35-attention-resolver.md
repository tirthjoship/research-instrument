# Sub-Project D — Phase 3.5: Attention-Data Resolver (unblock the live IC run)

**Why:** Phase 4 live run blocked. Broad-universe Wikipedia attention is invalid: `_load_wiki_map` covers only 8/518 tickers (1.5%); the rest query the raw ticker as an article title → wrong/stub pages (AIZ → "AIZ" stub ~2-11 views/day, not Assurant ~159/day). Also Wikimedia 429s bursts and the adapter swallows it as empty. Running the pre-registered gate on this = IC on noise. Fix the data layer first (honesty thesis, same as sub-projects A/B).

**Validated by probe (2026-06-06):** OpenSearch `action=opensearch&search=<longName>` resolves company names to correct articles for all 7 sampled S&P names (Assurant→Assurant 159/day, Akamai→Akamai Technologies 1246/day, etc.). View-volume ≥50/day cleanly separates real articles from stubs. IP not permanently blocked — HTTP 200 after burst cooldown.

**Branch:** `feat/leg2-subproject-d-divergence-ic-validation` (continue).

**Conventions:** domain pure stdlib; adapters import libs; inject HTTP/sleep callables for test fakes (never hit live APIs in tests); mypy strict; commit per green task; READ files before editing.

---

## Task R1: 429 backoff + SourceThrottledError in WikipediaPageviewsAdapter

**Files:** Modify `adapters/data/wikipedia_pageviews_adapter.py`; Test `tests/test_wikipedia_pageviews_adapter.py` (create if absent).

Current adapter swallows every `requests` exception (incl. 429) as `logger.warning + return []` — indistinguishable from a genuinely empty article. Mirror the `google_trends_adapter` pattern (raises `SourceThrottledError` from `domain/exceptions.py`).

- Add `max_retries: int = 3` param + an injectable `http_get` callable (default `requests.get`) and injectable `sleep` (default `time.sleep`) so tests don't hit network or wall-clock.
- On HTTP 429: retry with exponential backoff (`self._throttle_s * 2**attempt`), up to `max_retries`. If still 429 after retries → raise `SourceThrottledError(f"wikipedia throttled for {ticker}")`.
- Non-429 errors and genuine empties → unchanged (`warning + []`).
- Tests (fakes, no network): (a) 429-then-200 succeeds after one retry and returns parsed points; (b) persistent 429 raises `SourceThrottledError` after `max_retries`; (c) genuine empty `{"items":[]}` returns `[]` without raising; (d) non-429 error returns `[]`.
- The drip-backfill use case already maps `SourceThrottledError` into SourceHealth.throttled (sub-project B) — confirm by reading `DripBackfillUseCase`; if it catches throttle per-ticker, no change needed there. If it does NOT, the raise must be caught at the drip loop so one throttle doesn't abort the run — verify and note.

Commit: `feat: wikipedia adapter 429 backoff + SourceThrottledError (no silent empty)`

---

## Task R2: WikipediaArticleResolver adapter

**Files:** Create `adapters/data/wikipedia_article_resolver.py`; Test `tests/test_wikipedia_article_resolver.py`.

Pure-ish adapter, injectable `http_get` (default `requests.get`) + `sleep`.

- `resolve(name: str) -> str | None` — OpenSearch `https://en.wikipedia.org/w/api.php?action=opensearch&search=<name>&limit=1&namespace=0&format=json`; return `data[1][0]` (first title) or `None` if no hit.
- `mean_daily_views(article: str, start: datetime, end: datetime) -> float` — fetch pageviews REST (same endpoint family as the pageviews adapter), return mean views/day across returned items, `0.0` on empty/error. Article spaces → underscores; URL-encode.
- `resolve_validated(name: str, start, end, min_views: float = 50.0) -> str | None` — resolve, then return article only if `mean_daily_views >= min_views`, else `None` (stub/disambiguation guard).
- Tests (fakes): (a) opensearch hit returns title; (b) no hit → None; (c) resolve_validated rejects an article below min_views; (d) accepts above min_views; (e) URL-encoding of names with spaces/ampersands (e.g. "Arthur J. Gallagher & Co.").

Commit: `feat: WikipediaArticleResolver — name->article via OpenSearch + view-volume validation`

---

## Task R3: resolve-wiki-articles CLI + _load_wiki_map merge

**Files:** Modify `application/cli.py`; Test `tests/test_opportunity_cli.py`.

- New command `resolve-wiki-articles`: options `--market us`, `--limit 0`, `--min-views 50.0`, `--throttle-s 1.5`, `--out config/universe/wiki_articles_us.yaml`.
- Iterate `_get_ticker_universe(config)`. Skip tickers already present in themes.yaml aliases (curated, authoritative) AND tickers already in the out-YAML (resumable/idempotent).
- Company name via an injectable `name_provider: Callable[[str], str|None]` (CLI wires it to yfinance `longName`: read existing yfinance adapter; if `get_ticker_info` lacks the name, add a small `get_company_name(symbol) -> str | None` method that reads `ticker.info.get("longName")` — keep it minimal, behind try/except → None on failure). Test monkeypatches the resolver + name_provider so NO network.
- For each: name_provider → `WikipediaArticleResolver.resolve_validated(name, ...)`; on hit append `{ticker: article}` to the YAML (write incrementally so a crash keeps progress); track counts resolved / no_name / no_article / low_views / throttled. Print a SourceHealth-style summary.
- Extend `_load_wiki_map(market)`: after loading themes aliases, also load `config/universe/wiki_articles_<market>.yaml` (flat `{ticker: article}`) if present and merge — **aliases win** on conflict. Add a test that the merged map prefers the alias.
- CLI test: monkeypatch resolver + name_provider with fakes; assert the out-YAML gets the resolved entries and the summary prints; assert an already-aliased ticker is skipped.

Commit: `feat: resolve-wiki-articles CLI + merge resolved map into _load_wiki_map`

---

## After R1-R3: resume Phase 4 (Task 6)

1. `make check` green.
2. `python -m application.cli resolve-wiki-articles --throttle-s 1.5` (live, one-shot, resumable) → builds wiki_articles_us.yaml for ~510 names. Spot-check coverage + view sanity.
3. `python -m application.cli drip-backfill --source wikipedia --days 3650 --throttle-s 1.5` (now ~98% mapped; relies on R1 backoff for 429s).
4. Resume original plan Task 6 Step 3+ (run the gate, secondary horizons) → Task 7 verdict/ADR-044.
