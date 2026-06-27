# ADR-041: Honest Opportunity Engine — Keyless Attention Sources, Blended Divergence & Archive Backfill

**Date:** 2026-06-05
**Status:** Accepted
**Deciders:** Tirth Joshi

## Context

ADR-040 committed to evidence-first opportunity surfacing + multi-horizon forward-tracking. The first live `scan-opportunities` run (2026-06-05) abstained on all 34 thematic names. Investigation (not guessing — the project's ethos) found the abstention was structural, not a market condition or a simple threshold miss:

1. **The buzz pipeline was blind to mid-caps.** Persisted buzz came only from general-business RSS (`yahoo_finance`, `seeking_alpha`, `cnbc`); every buzzed ticker was a mega-cap. The emerging thematic names the engine exists to catch (ASTS, RKLB, LUNR, IRDM, OKLO, SMR, LEU…) had zero buzz rows ever. The Phase 3.5 mid-cap-capable sources never wrote a single row.
2. **The conviction bar was mathematically unreachable in bulk scan.** Weights total 8.0; `event_signal` + `analyst_signal` (weight 2.0) were hardcoded to neutral 5.0, so a strong-SEC name realistically landed ~5.5–5.8 and `cmin=6` failed by construction.
3. **Divergence had a cold-start artifact.** With only ~6 days of buzz history, the 37-day base window was empty, so `buzz_accel` pinned at max for any buzzed name — untrustworthy until weeks of history accrue.

A live source-health probe (2026-06-05) found: **StockTwits dead** (HTTP 403 on every ticker, API locked down); **Google Trends** never worked here (`pytrends` uninstalled); **GDELT** alive but throttled (429, honest archive to 2015); **RSS** mega-cap-only; **Reddit** not wired.

The honest reading: abstention was the engine truthfully telling us it could not see mid-cap attention. Lowering thresholds to manufacture large-cap calls would re-run the exact setup the conviction backtest rejected out-of-sample (ADR-039) — the self-deception those ADRs exist to prevent. The fix is to repair the engine's eyesight (sources + an honest historical base) and the miscalibrated bar (compute all dims), *then* track.

## Decision

Build **Leg-2 Sub-Project A — the Honest Opportunity Engine ("make the engine see honestly")**. Seven decisions:

1. **Retire the dead source.** StockTwits is deprecated and dropped from the pipeline — the public API returns 403 on every ticker. No effort spent reviving a locked-down source.

2. **Keyless-first source strategy with a pluggable Reddit.** Ship four keyless sources requiring no API key or per-call cost: **GDELT** (throttle-fixed), **Google Trends** (`pytrends`, installed), **Google News per-ticker RSS** (new), **Wikipedia pageviews** (new). **Reddit (PRAW)** is built as a pluggable adapter that activates only when credentials exist and is a logged no-op otherwise. This keeps the daily cycle free to run and never blocks on a missing key.

3. **Split attention into two ports by data shape.** Introduce **`AttentionSeriesPort`** (`get_attention_series → list[AttentionPoint]`) for **intensity** sources (Google Trends index, Wikipedia view counts) alongside the existing event-based **`BuzzDiscoveryPort`** (news/social discrete events). The split is structural, not cosmetic: a continuous interest *level* and a stream of discrete *events* have genuinely different shapes, and faking discrete events out of a continuous index (or vice versa) would be dishonest modeling. Each shape gets its own acceleration computed natively.

4. **Blend two honest accelerations into one divergence score.** `blended_divergence_score()` combines **event-acceleration** (recent-vs-base-rate event counts from news/social) and **intensity-acceleration** (recent-vs-base mean level from search/pageviews). Both ratios are scale-free, so GT's 0–100 index and Wikipedia's raw counts need no normalization. Weights adapt to available data: when one shape is absent, the present shape gets weight 1.0 (no zero-padding a missing signal); when both are absent, the score is neutral 5.0 (the unchanged honest abstain path).

5. **Honest archive backfill seeds the base window.** `BackfillHistoryUseCase` pulls genuinely archived attention per universe ticker — GDELT article timestamps (new `get_historical_buzz`), Google Trends weekly history, Wikipedia daily history — using each source's **real recorded date**, never a synthetic or reconstructed timestamp. It is append-only, deduped on `(ticker, source, ts)`, per-ticker failure-isolated, and idempotent. Reddit and Google News are excluded precisely because they lack an honest archive (live-only).

6. **Compute all-but-one conviction dimension in bulk scan, cached and flag-on-failure.** `ConvictionSignalCache` wires `analyst_signal` live (yfinance analyst-rating events) behind a 24h TTL cache (compute-on-miss). On fetch failure a dimension falls to an honest neutral 5.0 **with a logged flag row**, never a silent pin. `event_signal` remains held at neutral 5.0 in bulk scan — the Gemini event path needs a `NewsHeadlinePort` (AlphaVantage) + `GEMINI_API_KEY` per ticker, deferred to avoid per-ticker API cost/keys; the cache extension point exists for it. Conviction now reflects **7 of 8** dimensions in bulk scan (up from 6).

7. **Log the full candidate distribution; calibrate the bar from data; schedule locally.** `OpportunityScanUseCase` writes **every** candidate's scores (conviction, divergence, per-dim sub-scores, a `surfaced` flag) to `scan_candidates` *before* the surface/abstain cut; only above-bar calls are forward-tracked, preserving honest abstention. `scan-opportunities --show-all` prints the ranked distribution so `cmin`/`dmin` are calibrated from the observed spread, not hand-tuned. A new idempotent `daily-cycle` command chains scan → resolve → conditional weekly backfill, scheduled via a local **launchd** plist (`docs/scheduling.md`).

## Alternatives considered

- **Lower the thresholds to surface large-cap calls now** — rejected: re-runs the out-of-sample-failed setup (ADR-039), the precise self-deception this engine is built to avoid.
- **Revive StockTwits** — rejected: dead (403), not worth effort.
- **Paid attention data (premium social/alt-data feeds)** — rejected: cost + key management for a personal tool; the four keyless sources plus optional Reddit cover the need.
- **Reconstruct historical social state for a divergence backtest** — rejected: that is look-ahead bias. Only genuinely archived public values (GDELT/GT/Wikipedia) may seed the base window; this is forward-tracking infrastructure, not a backtest.
- **Cloud cron (GitHub Actions, per ADR-007)** — rejected here: the store is local SQLite and creds are local, so local scheduling is simpler. Intentional deviation, see Consequences.

## Consequences

**Positive:**

- The engine can finally **see mid-cap attention** — per-ticker Google News RSS + Wikipedia pageviews + GDELT history surface ASTS/RKLB/OKLO-class buzz that mega-cap-only RSS never wrote.
- Divergence is computed from a **populated base window** from day one — the cold-start max-pin artifact is solved, honestly.
- Conviction reflects **7 of 8** dimensions in bulk scan (was 6); thresholds are **empirically calibrated** from the logged distribution rather than guessed.
- The **full candidate distribution** is persisted every scan — the raw feed for bar-discrimination analysis (do above-bar names outperform below-bar?) and for Sub-Project B's eval harness.
- Source isolation, exponential backoff, and flag-on-failure mean **one dead/throttled source never crashes a scan**; the daily cycle tolerates partial source failure.

**Limitations & risks (do not oversell):**

- **This is not proven alpha.** Sub-Project A improves *surfacing coverage and honesty*, not demonstrated predictive edge. ADR-039 found **no statistically significant out-of-sample edge** in the backtestable slice; that finding stands.
- **The backfill is leakage-free for forward-tracking but is NOT a backtest.** It seeds the divergence base window from honest archive timestamps used only to compute a base-rate window. It must never be presented as evidence of predictive skill — only forward-tracked live outcomes (1w/1m/3m vs SPY + NDX) accrue honest evidence.
- **One dimension is still held neutral.** `event_signal` stays at 5.0 in bulk scan (per-ticker Gemini cost/keys deferred); conviction is 7/8, not 8/8.
- **Live sources are rate-limited.** GDELT and Google Trends throttle (429); backoff turns a 429 into a wait, but the daily cycle may legitimately abstain under heavy rate-limiting. `cmin`/`dmin` calibration (a local live diagnostic) can itself abstain when sources are throttled — that is a valid outcome, not a bug.
- **Scheduling deviates from ADR-007.** Local launchd, not cloud cron, because the DB and creds are local. The user must wire the trigger on their own machine.
- StockTwits removal is a breaking change for any caller still importing it; it is retired from the pipeline.
