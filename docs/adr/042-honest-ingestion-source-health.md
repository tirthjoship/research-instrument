# ADR-042: Honest Ingestion & Source Health — Leg-2 Sub-Project B

**Date:** 2026-06-05
**Status:** Accepted
**Deciders:** Tirth Joshi

> **Implementation pending.** Code has not been written yet. The decisions below are locked; execution follows the plan at `docs/superpowers/plans/2026-06-05-leg2-subproject-b-honest-ingestion.md`.

## Context

Sub-project A (ADR-041) shipped the honest opportunity engine on 2026-06-05. Within hours of the first live run the data layer surfaced a cluster of compounding failures:

| # | Finding | Consequence |
|---|---------|-------------|
| 1 | GDELT free tier 429s through all retries | 0 event-buzz archived; "honest event backfill" produced nothing silently |
| 2 | Google Trends rate-limits under burst load | Not viable for daily 350-ticker sweeps without spacing |
| 3 | Rate-limited sources return `[]`, not errors | Backfill reported "0 errors" while GDELT fully failed — blind to the most common failure mode |
| 4 | Backfill universe (alphabetical S&P 500) ≠ scan universe (thematic spine) | Scored tickers had no base window; the two universes never overlapped |
| 5 | Conviction compressed (floor 2.49, max 3.39 / 10) | `cmin=6.0` → permanent abstention; scale is degenerate |
| 6 | No joint signal (high-conviction ≠ high-divergence) | Layered trigger surfaces nothing — **but confounded by 1–4, not yet a real finding** |
| 7 | `cap_tier` labels every ticker "small" (incl. META/V/MU) | marketCap field not reaching the classifier |

The critical diagnostic: finding 6 (the conclusion that "the signal is degenerate") is computed on the broken inputs of findings 1–5. The edge question cannot be answered until the data layer is honest. This sub-project removes that confound.

Full design: `docs/superpowers/specs/2026-06-05-leg2-subproject-b-honest-ingestion-design.md`.

## Decision

Build **Leg-2 Sub-Project B — Honest Ingestion & Source Health**. Nine decisions:

1. **Prune, don't add.** This sub-project adds **no new model dimensions**. Prior phases accumulated signals hoping for edge; the evidence (ADR-039: no OOS edge, 46–49% full-universe backtest) says that adding signals is not the move. The honest path is fewer, sharper, reliable signals that can actually be evaluated. The conviction combiner is frozen — any redesign is gated on the clean-data re-evaluation that this sub-project enables.

2. **Throttle ≠ empty (data-integrity rule).** Adapters must return a distinguishable `SourceThrottledError` (or a structured "throttled" outcome) versus a genuine empty observation. A rate-limit must **never** be written as a zero or an empty array into the store — doing so poisons the divergence base window (the base rate appears lower than it is, artificially inflating future acceleration scores). This is a look-ahead-adjacent data-integrity rule: the base window must reflect reality, not the health of the network connection at fetch time.

3. **Source consolidation.** After live-run evidence on source reliability:
   - **Google News RSS** — primary event source. Keyless, mid-cap coverage, works.
   - **Wikipedia pageviews** — primary intensity source. Official API, reliable, honest daily history.
   - **Google Trends** — secondary. Slow-drip only (spaced / jittered); throttle-tolerant; not viable for burst sweeps.
   - **GDELT** — demoted to optional/off (flag-gated). Free tier 429s through all retries confirmed in the sub-project A live run; zero archived rows produced. Kept as a future upgrade path behind a flag, not in the default daily cycle.
   - **Reddit** — off without credentials (unchanged from ADR-041).
   - **StockTwits** — already retired (ADR-041).

4. **`SourceHealth` visibility — never silent.** A new `SourceHealth` value object (domain, sibling of `ConvictionSignalCache.flags`) tracks per-source: `attempts`, `ok`, `empty`, `throttled`, `failed`. Every drip run and nightly delta sweep returns a structured `SourceHealth` report. A source that throttled or failed is always visible in the run report and (if relevant) in the dashboard — never swallowed into a silent `[]`.

5. **Resumable spine-first slow-drip backfill.** Cold-start is the real cost, not daily limits. The store is append-only + deduped on `(ticker, source, ts)`, so warm state = 1 new day per ticker, trivially cheap. The `DripBackfillUseCase` therefore: (a) iterates the **scan universe** (thematic spine first, then discovery overlay), (b) spaces and jitters sleeps under rate budgets, (c) checkpoints via the store itself — if the latest row for a ticker is already today, skip it; a crash at ticker N resumes at N+1 for free (no separate state file). The `DailyDeltaSweepUseCase` then fetches only the window since the last stored observation per ticker. **No proxies, no multi-account farming** — both are ToS-evasion and contradict the honesty thesis this engine is built on.

6. **Minimum-history gate (`has_min_history` — ~21 days).** A pure domain predicate: a ticker is ineligible to surface until it has ≥ `MIN_HISTORY_DAYS` observations in its base window. Prevents day-1 noise spikes caused by a single article inflating the acceleration ratio before any stable base rate exists.

7. **Discrimination audit — evidence before pruning.** `DiscriminationAuditUseCase` is a one-shot diagnostic (not in the daily path) that, for the current candidate set, dumps per-dimension and per-source distributions: variance, percentage of neutral scores, and contribution to final conviction. Output is a human-readable report; the human reads it and decides which dims/sources to prune. No automatic pruning — the audit surfaces evidence, the decision is deliberate. Applied in a follow-up so this sub-project stays scoped.

8. **Honest empty-state in the dashboard.** When the engine abstains, the dashboard shows the full ranked `--show-all` candidate distribution, the top near-misses, and the source-health panel. "Here is everything I looked at, and here is why nothing cleared the bar" reads as analytical rigor, not a broken tool. Abstention is a valid outcome; hiding it is not.

9. **Local scheduler constraint — documented, not hidden.** The nightly drip and delta sweep run under launchd (established in ADR-041: local SQLite → local scheduler, intentional deviation from ADR-007 GitHub Actions). **`caffeinate` is required** — launchd will not fire on a closed-lid or sleeping laptop. This constraint is documented in `docs/scheduling.md`, not solved by infra in this sub-project. The daily scan + resolve loop keeps running regardless of surfacing: accumulating resolved out-of-sample outcomes is wall-clock-bound and starts immediately.

## Alternatives considered

- **Add more sources to recover coverage** — rejected: the problem is source reliability and data-integrity rules, not source count. Adding unreliable sources compounds the poisoning problem.
- **Proxies or multi-account requests to bypass rate limits** — rejected: ToS-evasion, fragile, directly contradicts the "honest" thesis of this entire Leg-2 arc.
- **Automatic pruning in the discrimination audit** — rejected: evidence informs the decision; the human makes the cut. Automatic pruning risks removing dimensions before their full base window has accumulated.
- **Redesign the conviction combiner in this sub-project** — rejected: gated on the clean-data re-evaluation; changing the combiner before that run would obscure whether improvements came from better data or a different formula.
- **Cloud cron for the nightly sweep** — rejected: the store is local SQLite and credentials are local; local launchd is simpler. The `caffeinate` constraint is the honest cost of that choice.

## Consequences

**Positive:**

- The data layer becomes **self-reporting**: every run surfaces per-source `SourceHealth`, eliminating the silent `[]` failure mode that caused finding 3.
- The **throttle-≠-empty rule** removes the base-window poisoning that made conviction scores degenerate (finding 5). Divergence scores will reflect genuine attention patterns, not network failures.
- **Spine-first backfill aligned to the scan universe** means scored tickers will have a populated base window — the core structural gap in sub-project A (finding 4) is closed.
- The **minimum-history gate** blocks day-1 false spikes before they reach the surface trigger.
- The **discrimination audit** produces evidence for principled pruning — dead dimensions are identified by data, not by guess.
- The **honest empty-state** turns abstention into a legible product outcome rather than a silent failure.
- The daily scan + resolve loop continues accumulating forward-tracked outcomes throughout — wall-clock evidence accrues from day one.

**Limitations & risks (do not oversell):**

- **This fixes data reliability, not proven edge.** ADR-039's finding — no statistically significant out-of-sample edge in the backtestable slice — stands unchanged. The clean-data re-evaluation (what finding 6 becomes on honest inputs) is a future measurement, not a current result.
- **The no-joint-signal finding (finding 6) is confounded** by broken data from findings 1–4. It will be re-evaluated once the data layer is honest. Sub-project B removes the confound; it does not claim the signal will materialize.
- **Cold-start is slow by design.** The spine (~40 tickers) warms in roughly one night at 1 Trends request / 45–60s jittered. The full 350-ticker universe drips in the background over subsequent nights. This is the honest cost of rate-aware operation without ToS evasion.
- **GDELT demotion is a regression in event-buzz coverage.** Google News RSS covers live events well but has no honest archive. The archive gap means event-acceleration for older base-window tickers relies on the honest archive sources (Trends, Wikipedia). This is the right trade-off — a present but unreliable source is worse than an absent one.
- **`caffeinate` or equivalent is required for scheduled nightly runs.** This is an undeniable operational constraint on a local-machine scheduler.
- **Conviction combiner is frozen.** Any change to weighting or aggregation logic is gated on the discrimination audit report and the clean-data scan results, not built here.
