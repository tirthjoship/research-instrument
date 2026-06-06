# Leg-2 Sub-Project B — Honest Ingestion & Source Health (Design Spec)

**Date:** 2026-06-05
**Status:** Draft (pending user review)
**Branch:** `feat/leg2-subproject-b-honest-ingestion`
**Predecessors:** ADR-039 (no OOS edge), ADR-040 (forward-tracking), ADR-041 (honest opportunity engine), Leg-2 sub-project A.

---

## 1. Goal

Make the opportunity engine's data layer **reliable, look-ahead-safe, and self-reporting**, so the signal can finally be evaluated on clean inputs instead of broken ones. This sub-project fixes plumbing and prunes dead weight — it deliberately adds **no new model dimensions**.

The guiding stance, agreed during brainstorming: **prune, don't add.** Prior phases accumulated signals hoping for edge; the evidence (ADR-039, 46-49% full-universe backtest) says edge is not present in free data. The reasonable path from here is reliability + honesty + consolidation.

---

## 2. Why now — findings that forced this

From shipping + running sub-project A live (2026-06-05):

| # | Finding | Consequence |
|---|---------|-------------|
| 1 | GDELT free tier 429s through all retries | 0 event-buzz archived; ADR-041's "honest event backfill" produced nothing |
| 2 | Google Trends rate-limits under burst load | Not viable for daily 350-ticker sweeps without spacing |
| 3 | Rate-limited sources return `[]`, not errors | Backfill reported "0 errors" while GDELT fully failed — blind to the commonest failure mode |
| 4 | Backfill universe (alphabetical S&P500) ≠ scan universe (thematic spine) | Scored tickers had no base window; the two universes never met |
| 5 | Conviction compressed (floor 2.49, max 3.39 / 10) | `cmin=6.0` → permanent abstention; scale is degenerate |
| 6 | No joint signal (high-conviction ≠ high-divergence) | Layered trigger surfaces nothing — **but confounded by 1-4, not yet a real result** |
| 7 | `cap_tier` labels every name "small" (incl. META/V/MU) | marketCap not reaching the classifier |

**Core diagnosis:** finding 6 (the "signal is degenerate" conclusion) is computed on the broken inputs of findings 1-5. We cannot judge the model until the data layer is honest. This sub-project removes that confound.

---

## 3. Scope

### In scope (v1)
- Resumable, rate-aware **slow-drip backfill** aligned to the **scan universe** (spine + discovery first).
- **Delta-only nightly sweep** (fetch new days only; warm store stays cheap).
- **Source-health accounting** — minimal: per-source success/fail/throttle counts + flags, surfaced to the user.
- **Data-integrity rules** — throttle ≠ 0; honest observation timestamps (no look-ahead); minimum-history gate.
- **cap_tier bug fix.**
- **Source consolidation** — demote GDELT to optional; primary event source = Google News RSS (keyless, works).
- **Dim/source discrimination audit** — one-shot diagnostic: which dims/sources actually vary and contribute; drop dead weight.
- **Honest empty-state** in the dashboard — distribution + near-misses + source health when the engine abstains.

### Out of scope (deferred — explicitly)
- Full 350-ticker cold start (drips in the background **after** v1 ships on the spine).
- Intraday / few-minute hot-list rescans (no short-horizon consumer exists yet).
- Any new model dimension. Any Gemini/paid path. Any proxy / multi-account scheme (rejected: ToS-evasion, fragility, contradicts the honesty thesis).
- Model redesign (conviction combiner changes) — that is a **decision gated on the clean-data re-evaluation**, not a build item here.

---

## 4. Architecture

Hexagonal, consistent with the existing codebase. New behavior lives in **application use cases** + small adapter changes; the domain stays pure.

```
adapters/data/*      →  domain/ (pure)  ←  application/ (orchestration)
   (sources, store)      (models, rules)     (drip, sweep, audit)
```

### 4.1 Components (each one job, testable in isolation)

1. **`DripBackfillUseCase`** (new, application)
   - Iterates the **scan universe** (spine + discovery), spaced + jittered sleeps.
   - **Resumable:** skips any ticker whose latest `attention_series`/buzz row is already today (checkpoint via the store, not a side file). A crash at ticker N resumes at N+1 for free — store is append-only + deduped.
   - Per-ticker, per-source isolation (one failure logs + continues).
   - Returns a structured run report (see source health).

2. **`DailyDeltaSweepUseCase`** (new, application — or a thin mode of the drip)
   - Fetches only the window since the last stored observation per ticker. Steady-state = 1 new day × universe.
   - Same resumability + isolation.

3. **`SourceHealth`** (new, small — domain value object + store table or in-report aggregation)
   - Per source: `attempts, ok, empty, throttled, failed`. A source that throttled is **visible**, never silent.
   - Reuses the existing `ConvictionSignalCache.flags` pattern; this is its sibling at the ingestion layer.

4. **Data-integrity rules** (domain + adapter contracts)
   - **Throttle ≠ 0:** adapters must return a distinguishable "throttled/failed" outcome vs "genuinely empty." The drip writes a value **only** for real observations; throttle writes nothing.
   - **Honest timestamps:** each stored row's `ts` = the true observation date from the source payload, never the fetch time. (Project rule #1: no look-ahead.)
   - **Minimum-history gate** (pure domain predicate): a ticker is ineligible to surface until it has ≥ `MIN_HISTORY_DAYS` of base-window observations. Prevents day-1 noise spikes.

5. **`DiscriminationAuditUseCase`** (new, application — diagnostic, run once, not in the daily path)
   - For the current candidate set, dump per-dim and per-source distributions (variance, % neutral, contribution to final conviction).
   - Output is a report the human reads to decide which dims/sources to **prune**. No automatic pruning — surfaces the evidence.

6. **`cap_tier` fix** (adapter/use-case bug)
   - Ensure marketCap reaches the classifier (batch yfinance info or persisted field). Add a regression test asserting a known mega-cap classifies as `large`.

7. **Dashboard honest empty-state** (adapter/visualization)
   - When the scan abstains: show the ranked `--show-all` distribution, the top near-misses, and the source-health panel. "Here's everything I looked at and why nothing cleared the bar" reads as rigor, not failure.

### 4.2 Source strategy after consolidation

| Source | Shape | Status after v1 |
|--------|-------|-----------------|
| Google News RSS | event (volume) | **Primary event source** (keyless, reliable) |
| Wikipedia pageviews | intensity | **Primary intensity source** (official API, reliable) |
| Google Trends | intensity | **Secondary** — slow-drip only, throttle-tolerant |
| GDELT | event | **Optional/off** — free tier unusable; kept behind a flag |
| Reddit (PRAW) | event | Off unless creds present (unchanged) |
| StockTwits | — | Retired (unchanged) |

---

## 5. Scheduling

Local launchd (ADR-007 consequence: local SQLite → local scheduler), per existing `docs/scheduling.md`.
- Overnight **drip/delta sweep**, spaced under rate limits.
- **Known constraint (documented, not hidden):** launchd will not run on a closed-lid/asleep laptop. v1 documents the `caffeinate` requirement or accepts "runs when awake." This is an honest local limitation, not solved by infra in this sub-project.
- The daily **scan + resolve loop keeps running regardless of surfacing** — accumulating resolved out-of-sample outcomes is the only thing that can ever settle the edge question, and it is wall-clock-bound, so it starts immediately.

---

## 6. Rate-budget reasoning (the throughput answer)

The limit is **cold-start, not daily**. The store is append-only + deduped, so:
- **Cold (day 1):** 90 days × universe — slow, one-time. Spine (~40) ≈ one night at 1 Trends req / 45-60s.
- **Warm (steady state):** 1 new day × universe — trivial, fits any limit.

So v1 warms the **spine** once, ships, and **drips the 350 in the background** over subsequent nights. No proxies, no account farming.

---

## 7. v1 Acceptance Criteria

- Spine (~40) cold-started, all eligible names ≥ `MIN_HISTORY_DAYS`; 350 dripping in background.
- Nightly delta sweep scheduled; resumable across crashes; source health logged + visible.
- Adapters distinguish throttle/fail from empty; stored timestamps proven to be observation-dated (tested).
- `cap_tier` correct (regression-tested on a known mega-cap).
- Discrimination audit report produced; pruning decisions recorded (which dims/sources kept vs dropped).
- Scan emits a ranked distribution + honest verdict (surface **or** abstain-with-evidence).
- Dashboard renders the honest empty-state.
- `make check` green, mypy strict, ≥90% coverage; feature → develop → main with green CI.
- **Not required:** proven edge, full 350 coverage, intraday tier, any new model dim.

---

## 8. Risks & pitfalls (carried from brainstorming)

1. **Cold-start wall-clock vs deadline** → mitigated by spine-first scope; 350 deferred.
2. **Throttle-0 poisoning the base window** → throttle writes nothing; integrity rule + test.
3. **Look-ahead via fetch-dated rows** → observation-date provenance + per-source test (project rule #1).
4. **Crash restarts burning rate budget** → store-checkpoint resumability + crash-resume test.
5. **Thin-history false spikes** → minimum-history gate before eligibility.
6. **Abstention looks broken** → honest empty-state UX.
7. **"Useful by ship ≠ proven by ship"** → expectation set; tracking starts, edge unproven by design.
8. **Laptop scheduler silently not firing** → documented `caffeinate` constraint.
9. **Over-engineering reflex** → no new dims; consolidate sources; discrimination audit drives pruning.

---

## 9. Open questions for review

- `MIN_HISTORY_DAYS` value (proposal: 21 — enough base window for a stable acceleration ratio).
- Drip spacing for Trends (proposal: 45-60s jittered).
- Whether the discrimination audit's pruning is applied **in this sub-project** or recorded for a follow-up. (Proposal: record here, apply in a small follow-up so v1 stays scoped.)
