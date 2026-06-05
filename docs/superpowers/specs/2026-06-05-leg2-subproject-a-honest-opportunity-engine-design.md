# Leg-2 Sub-Project A — Honest Opportunity Engine (Make the Engine See)

**Date:** 2026-06-05
**Status:** Design approved — pending implementation plan
**Deciders:** Tirth Joshi
**Branch:** `feat/opportunity-forward-tracking`

## Context & Motivation

The first live `scan-opportunities` run (2026-06-05) abstained on all 34 thematic
names. Investigation (not guessing — the project's ethos) found the abstention was
**not** a market condition or a simple threshold miss. It surfaced three stacked
structural causes plus a dead data source:

1. **Buzz pipeline is blind to mid-caps.** Persisted buzz comes only from
   general-business RSS (`yahoo_finance`, `seeking_alpha`, `cnbc`); every buzzed
   ticker is a mega-cap (AAPL, NVDA, META…). The emerging thematic names the engine
   exists to catch — ASTS, RKLB, LUNR, IRDM, OKLO, SMR, LEU, KTOS, KRYS, VKTX — have
   **zero** buzz rows, ever. The Phase 3.5 mid-cap-capable sources never wrote a
   single row.
2. **Conviction bar mathematically unreachable in bulk scan.** Weights total 8.0;
   `event_signal` + `analyst_signal` (weight 2.0) are hardcoded to neutral 5.0. To
   clear an overall 6.0, the 6 live dims (weight 6.0) must average 6.33 — while
   `ml_direction` (w=0.3) defaults to 5.0 and `sentiment_momentum` is starved. A
   strong-SEC name realistically lands ~5.5–5.8. `cmin=6` fails by construction.
3. **Divergence cold-start artifact.** Only 6 days of buzz history exist; the
   37-day base window is empty, so `buzz_accel` pins at max for any buzzed name —
   untrustworthy until ~6 weeks of history accrue.

**Recon on the source health (live probe, 2026-06-05):**

| Source | Verdict | Evidence |
|--------|---------|----------|
| StockTwits | **DEAD** | HTTP 403 Forbidden on every ticker incl. NVDA. API locked down. |
| Google Trends | Never worked here | `No module named 'pytrends'` — dependency uninstalled. |
| GDELT | Alive, throttled | HTTP 429 — transient rate-limit, not dead. Honest history to 2015. |
| RSS | Works, mega-cap-only | (known) |
| Reddit | Not wired | absent from `daily-scan`. |

**Conclusion that frames this sub-project:** abstention is the engine honestly
telling us it cannot see mid-cap buzz. Lowering thresholds to manufacture large-cap
calls would re-run the exact setup the conviction backtest already rejected
out-of-sample (ADR-039/040) — the self-deception those ADRs exist to prevent. The
honest path is to fix the engine's eyesight (sources + honest historical base),
fix the miscalibrated bar (compute all dims), *then* track.

## Scope

This spec covers **Sub-Project A — "make the engine see honestly":** buzz source
coverage, honest historical backfill, conviction calibration, full-distribution
logging, and a schedulable daily cycle. Outcome: the daily scan surfaces real
mid-cap opportunities on mature, honest signals and begins accruing forward-tracked
evidence.

**Deferred to Sub-Project B ("self-maintaining"):** the eval harness, drift-flag
detection, and self-healing/auto-recalibration layer extending Phase 9
`pattern_service`. B depends on A producing flowing data and is brainstormed
separately once that data exists.

## Locked Decisions

| # | Decision | Choice |
|---|----------|--------|
| Q1 | Live buzz sources | Source-pluggable pipeline. Ship now with **4 keyless sources** — GDELT (throttle-fixed), Google Trends (install pytrends), Google News per-ticker RSS (new), Wikipedia pageviews (new). **Reddit (PRAW)** built as a pluggable adapter, activates when creds exist. StockTwits retired (dead). |
| Q2 | Divergence + intensity modeling | **Blend two honest sub-signals**: event-acceleration (news/social) + intensity-acceleration (GT/Wikipedia). Each computed natively for its data shape; no faked events from a continuous index. |
| Q3 | Conviction fix | **Wire all 8 dims** (compute `event_signal` via Gemini, `analyst_signal` via yfinance/Finnhub) behind a **daily cache**; calibrate `cmin`/`dmin` from the observed distribution, not a guess. |
| Q4 | Surfacing policy | **Surface above-bar + log the full candidate distribution.** Forward-track only above-bar calls (honest abstention preserved); persist every candidate's scores for calibration, bar-validation, and B's eval harness. |

## Architecture & Component Map

Stays within hexagonal structure: new sources are adapters, new signals are pure
domain, orchestration is application. No reaching into domain internals.

### New ports (`domain/ports.py`)
- **`AttentionSeriesPort`** — `get_attention_series(ticker, start, end) -> list[AttentionPoint]`
  for intensity sources (Google Trends, Wikipedia). Distinct from the event-based
  `BuzzDiscoveryPort` (news/social) because the data shape differs — Q2 made
  structural.

### New / changed adapters (`adapters/data/`)
| Adapter | Port | Shape | Notes |
|---------|------|-------|-------|
| `google_news_adapter.py` *(new)* | BuzzDiscoveryPort | events | per-ticker News RSS by company alias; live-only |
| `wikipedia_pageviews_adapter.py` *(new)* | AttentionSeriesPort | intensity | Wikimedia REST; honest daily history |
| `reddit_adapter.py` *(new)* | BuzzDiscoveryPort | events | PRAW; **no-op if creds absent** (pluggable) |
| `gdelt_sentiment_adapter.py` *(fix)* | BuzzDiscoveryPort + history | events | add exponential backoff + cache; add `get_historical_buzz` (article timestamps → events) |
| `google_trends_adapter.py` *(fix)* | AttentionSeriesPort | intensity | install pytrends; already has `get_historical_interest` |
| `stocktwits_adapter.py` *(retire)* | — | — | mark deprecated, drop from pipeline (dead/403) |

### New domain (`domain/`)
- **`AttentionPoint`** model `(ticker, timestamp, value, source)` — immutable, point-in-time.
- **`divergence_service.py` extended** — keep `divergence_score` (events) intact; add
  `intensity_acceleration(...)`; add `blended_divergence_score(...)`. Pure, no I/O.

### New / changed application (`application/`)
- **`backfill_use_case.py` (new)** — `BackfillHistoryUseCase`: pull GDELT events +
  GT/Wikipedia intensity history per universe ticker → persist. One-time + weekly refresh.
- **`opportunity_scan_use_case.py` extended** — gather intensity series, compute blended
  divergence, persist the full candidate distribution.
- **`conviction_signal_cache.py` (new)** — wraps cached event/analyst computation; injected
  into the scan's conviction provider. `cli.py` provider stops hardcoding 5.0.

### New store tables (SQLite)
- **`attention_series`** `(ticker, source, ts, value)`
- **`scan_candidates`** `(scan_date, ticker, conviction, divergence, sub_scores_json, surfaced, theme, cap_tier)` — full-distribution log
- **`signal_cache`** `(ticker, dim, value, computed_at)` — daily TTL for event/analyst

### New / changed CLI
- **`backfill-history`** (new) · **`scan-opportunities --show-all`** (extend) ·
  **`daily-cycle`** (new: scan → resolve → weekly backfill-if-due) ·
  existing `resolve-calls` / `opportunity-report` unchanged.

### Dependencies & config
- **Deps:** add `pytrends`; `praw` as an optional extra.
- **`config/universe/themes.yaml`:** per-ticker aliases (company name, cashtag, subreddits)
  for query mapping. Derive a default from yfinance `longName` where unset.
- **`config/markets/us.yaml`:** source toggles, cache TTLs, blend weights `w_e`/`w_i`,
  calibrated `cmin`/`dmin`.

## Divergence Blend (pure, `divergence_service.py`)

Existing event-divergence logic is unchanged; it is generalized so each data shape
computes acceleration natively, then blends.

**Event acceleration** (news/social — GDELT, Google News, Reddit):
```
recent      = events in [now-7d, now]
base_rate   = (events in [now-37d, now-7d] / 30) * 7
event_accel = (recent - base_rate) / max(recent, base_rate, 1)        # ~[-1, 1]
```

**Intensity acceleration** (Google Trends index, Wikipedia views):
```
recent_level    = mean(intensity in [now-7d, now])
base_level      = mean(intensity in [now-37d, now-7d])
intensity_accel = (recent_level - base_level) / max(recent_level, base_level, eps)  # ~[-1, 1]
```
The ratio is **scale-free**, so GT's 0–100 index and Wikipedia's raw view counts need no
normalization. When multiple intensity sources are present, compute `intensity_accel` per
source and **average across available sources** (each already scale-free).

**Blend** (one final score; weights adapt to available data):
```
blended_accel = w_e*event_accel + w_i*intensity_accel        # w_e + w_i = 1; default 0.5/0.5 in us.yaml
                                                             # if one shape absent, the present shape gets weight 1.0
price_move    = max(recent_return, 0)
raw           = blended_accel - price_move*2                 # "attention up, price flat" = thesis
divergence    = clamp(5.0 + raw*5.0 + (sentiment-0.5)*2, 1, 10)
```

**Graceful degradation (no faking):**
- no events **and** no intensity → neutral **5.0** (unchanged abstain path)
- only one shape present → that shape gets weight 1.0 (no zero-padding a missing signal)
- both present → configured blend

## Honest Backfill (`BackfillHistoryUseCase`)

Per universe ticker, pull **real archived** attention over a default **90-day**
window (base 37d + buffer + regime context):

| Source | Method | Shape → table |
|--------|--------|---------------|
| GDELT | `get_historical_buzz(t, start, end)` *(new: article timestamps → events)* | `buzz_signals` |
| Google Trends | `get_historical_interest` *(exists)* | `attention_series` |
| Wikipedia | `get_attention_series` *(new)* | `attention_series` |
| Reddit / Google News | — *(no honest history → live-only, skipped)* | — |

**Honesty guardrails:**
- Every backfilled timestamp is the source's **real** recorded date (GDELT article date,
  GT week, Wikipedia day). No synthetic timestamps, no reconstructed "what we'd have thought."
- Append-only, deduped on `(ticker, source, timestamp)` — re-running never double-counts;
  raw responses cached (ADR-017).
- Legitimate where a divergence *backtest* would not be: we read a genuine public archive of
  values that existed at those moments, not inferred past social state. Reddit / Google News
  are excluded precisely because they lack an honest archive.

**Result:** the divergence base window is populated from day one → cold-start artifact (#3)
solved, honestly. `backfill-history` runs once on setup; a weekly refresh extends the window
and covers new tickers.

## Conviction Wiring, Calibration, Distribution Log

### Wire the 2 dead dims, cached (Q3)
- **event_signal** → reuse Phase 4D `GeminiEventClassifier` over recent headlines
  (GDELT/Google News already pulled) → `event_conviction_score`.
- **analyst_signal** → reuse the `AnalystRatings` adapter (yfinance/Finnhub, free) →
  `analyst_conviction_score`.
- **`signal_cache`** (TTL 24h): scan checks cache → fresh hit reused, else compute + store.
  A daily job over ~50 tickers stays cheap; re-runs near-free.
- **Failure = honest neutral, flagged** — on rate-limit/fetch failure, the dim falls to 5.0
  with a logged warning + a flag row, never a silent pin. (Flag seeds B's source-health monitor.)
- Cleanup: the current provider calls `engineer.compute()` twice (dead duplicate) — collapse to one.

### Calibrate cmin/dmin from data
- `scan-opportunities --show-all` runs the full scan, prints the ranked candidate distribution
  (conviction, divergence, per-dim sub-scores), and persists it regardless of surfacing.
- Run once post-wiring → read the spread → set `cmin`/`dmin` at a sensible separation point
  (e.g. top-quartile knee) → store in `us.yaml`. Evidence-based, manual in A.
  *Auto*-recalibration from drift is Sub-Project B.

### Full-distribution log (Q4)
- `OpportunityScanUseCase.execute()` writes **every** candidate's scores to `scan_candidates`
  *before* the surface/abstain decision.
- Above-bar calls additionally persist to `surfaced_calls` (existing) and are forward-tracked by
  `resolve-calls`.
- Powers cmin calibration, bar-discrimination analysis (do above-bar names outperform below-bar?),
  and is the raw feed for B's eval harness.

## Scheduling

- New **`daily-cycle`** command = `scan-opportunities` → `resolve-calls` → weekly
  `backfill-history` refresh if due. One idempotent command.
- **Cadence:** pre-market **~8:00 ET** (captures overnight buzz, dates calls before the day's
  move, clean 1w/1m/3m horizons). Resolve runs every cycle, acting only on due horizons.
- **Mechanism:** the store is local SQLite, so local **launchd/cron** (or `/schedule`) fits
  better than GitHub Actions for this personal tool. **Deviation from ADR-007** (which chose
  GitHub Actions for cloud orchestration) is intentional and noted: a local DB + local creds is
  simpler scheduled locally. A ships the command + a documented launchd plist; the user wires the
  trigger (needs their machine + creds).

## Error Handling (one consistent discipline)

- **Source isolation** — every adapter catches network/parse errors → returns `[]` + logged
  warning. One dead source never crashes a scan.
- **GDELT/GT throttle** — exponential backoff + retry + raw-response cache → 429 becomes a wait,
  not a failure.
- **Reddit no-creds** — adapter is a logged no-op (pluggable), not an error.
- **Conviction dim failure** — neutral 5.0 + flag row, never silent.
- **tz-awareness** — the shipped `_match_awareness` boundary coercion covers all new stored
  timestamps.
- **Backfill** — per-ticker isolation: one ticker's failure logs + continues; append-only so
  it's resumable/partial-safe.
- **No silent caps** — if backfill hits `maxrecords` or a source caps results, log exactly what
  was dropped.
- **Abstention is a valid outcome**, not an error.

## Testing (AGENTS.md standards)

- **Fakes for every new adapter/port** — `FakeAttentionSeries`, `FakeGoogleNews`,
  `FakeRedditBuzz`, fake GDELT history. No live APIs in CI (rule #5).
- **Hypothesis property tests on the blend** — always in [1,10]; no-data → 5.0; higher
  attention-accel ⇒ divergence non-decreasing; single-shape input ≡ pure single-signal computation;
  higher price_move ⇒ divergence non-increasing.
- **Backfill tests** — idempotency (re-run, no dupes), per-ticker isolation, honest-timestamp
  preservation.
- **Conviction-cache tests** — hit / miss / TTL-expiry, failure → flagged-neutral.
- **Distribution-log tests** — every candidate persisted, `surfaced` flag correct.
- `make check` green — mypy strict, black, ruff, 90% coverage floor (repo at 93%). The two tz
  regression tests already shipped (commit `67a0a04`).

## Out of Scope (Deferred to Sub-Project B)

- Eval harness, drift-flag detection, self-healing / auto-recalibration of weights & thresholds
  (extends Phase 9 `pattern_service`).
- Portfolio construction, position sizing, two-sided (buy + sell) discipline, real-money
  execution (Leg-2 Sub-Project 2).
- SEC 8-K catalyst parsing (higher-effort source; recommended future add).
- Universe expansion beyond the current themes.yaml spine + buzz overlay (note as future).

## Success Criteria

1. A live scan surfaces **mid-cap** thematic names when their attention genuinely accelerates —
   i.e., the engine can see ASTS/RKLB/OKLO-class buzz, not only mega-caps.
2. Conviction reflects all 8 dims; `cmin`/`dmin` are set from the observed distribution and
   documented in `us.yaml`.
3. Divergence is computed from a populated (backfilled) base window — no cold-start artifact.
4. Every scan persists the full candidate distribution; above-bar calls are forward-tracked.
5. `daily-cycle` runs end-to-end, idempotent, with graceful degradation when a source is down.
6. `make check` green; all new sources faked in CI; honesty guardrails enforced by tests.
