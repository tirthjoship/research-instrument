# Leg-2 Sub-Project D — Divergence IC Falsification + Forward Clock (Design + Pre-Registration)

**Date:** 2026-06-05
**Status:** Draft (pending user review + pre-registration lock)
**Branch:** `feat/leg2-subproject-d-divergence-ic-validation`
**Predecessors:** ADR-039 (no OOS edge), ADR-041/042/043, methodology review 2026-06-05.

> **This document is also a PRE-REGISTRATION.** Section 4 locks the hypothesis, data, metric, and kill-criteria *before any result exists*. Once you approve it, we do not change Section 4 after seeing numbers. Exploratory analyses are allowed but must be labeled exploratory and cannot move the gate.

---

## 1. Goal & honest framing

Determine, as cheaply and honestly as possible, whether the **intensity-divergence signal** (rising attention vs flat/down price) has any cross-sectional predictive power — then, only if it survives, start the forward-tracking clock that is the *real* validation.

Two hard truths from the methodology review drive the design:
- **A clean historical backtest is impossible** on this project's data (no point-in-time universe → survivorship + look-ahead-in-selection; GDELT event-source dead). The repo already documents this (`CONTEXT.md:262`, ADR-039, forward-tracking spec).
- Therefore the backtest's **only honest job is falsification**: if divergence shows no signal even on a survivor-biased sample that *flatters* it, the signal is dead — kill it cheaply. A positive result is **necessary but not sufficient** (it's inflated by bias) and only earns the right to forward-track. **Real validation = the forward clock, which is wall-clock-bound (months).**

There is no fast path to evidence-based real money. This sub-project gives a cheap *kill switch* and starts the slow *real* clock.

---

## 2. The signal under test (precise)

Intensity-divergence at date T for ticker i, computed point-in-time (only data with observation date ≤ T):
- `intensity_acceleration` of **Wikipedia daily pageviews** over recent(7d) vs base(30d) windows (`domain/divergence_service.py:34`).
- minus clamped recent price up-move (`_recent_return`, ≥0).
- We test the **continuous divergence value**, not the `[1,10]` gate, and **intensity-only** (GDELT is dead; Google Trends is weekly + rate-limited → excluded from the primary test to keep it clean, daily, and feasible; Trends is a labeled secondary).
- Sentiment tilt **excluded** from the primary signal (isolate the attention-divergence hypothesis; sentiment is an exploratory variant).

Rationale for Wikipedia-only primary: it is the single attention source that is keyless, **daily**, leakage-free (real observation dates), and deep (2015→present). One API call returns a full multi-year daily series per article → backfilling the broad universe is ~hundreds of requests, minutes of wall-clock, no rate-limit issue.

---

## 3. Architecture (reuse-heavy; minimal new code)

Hexagonal, reusing the validation engine that already exists.

1. **Backfill broad-universe Wikipedia attention** — use the existing `DripBackfillUseCase` (sub-project B) with **Wikipedia source only** (no Trends/GDELT, so no throttle), over the broad universe (S&P 500 + NASDAQ-100, ~605 names), full available history. Idempotent append-only `attention_series`.
2. **`compute_cross_sectional_ic`** (new pure function, `application/ic_analysis.py`) — given per-date {ticker: signal} and {ticker: forward_return}, compute daily Spearman rank-IC, then aggregate (mean IC, IC t-stat/IR, % positive dates). Pure, unit-tested with fakes.
3. **`DivergenceICBacktestUseCase`** (new, `application/divergence_ic_backtest.py`) — point-in-time loop over scan dates × universe: compute intensity-divergence (reusing `divergence_service`) from `attention_series` (≤ T) + price (≤ T, yfinance), compute forward returns (`price_returns.compute_forward_return`), call `compute_cross_sectional_ic`, then run significance via the **existing** `date_level_significance` + `moving_block_bootstrap` (`precision_metrics.py`) and decile monotonicity (`monotonic_precision_curve`). Output a JSON report.
4. **CLI:** `validate-divergence-ic` — pre-registered params from a config block; writes `data/reports/divergence_ic_<date>.json`.
5. **Conditional Phase (gate):** *only if the IC test passes Section 4*, implement minimal **divergence-led surfacing** (intensity-divergence primary gate + `has_min_history` + abstention) and schedule the daily scan→resolve loop (launchd, existing `docs/scheduling.md`), and slice `CallOutcome` by divergence bucket (the absent join). This starts the forward clock on a non-falsified signal.

No new model dims. No paid sources. No proxies.

---

## 4. PRE-REGISTRATION (lock before running — do not change after seeing results)

**Hypothesis (H1):** intensity-divergence at date T has a positive cross-sectional Spearman IC vs forward returns at the primary horizon, on the broad universe, 2016–2025.
**Null (H0):** mean IC = 0.

**Locked parameters:**
- **Universe:** current S&P 500 + NASDAQ-100 (~605 names) — *broad, not the 27-name thematic spine* (reduces hindsight). Survivorship bias acknowledged as a **flattering** distortion (see falsification logic).
- **Attention source:** Wikipedia daily pageviews only. (Trends = secondary/exploratory.)
- **Signal:** intensity-divergence, intensity-only, sentiment excluded; windows recent=7d / base=30d (current defaults).
- **Sample period:** 2016-01-01 → 2025-12-31 (Wikipedia depth from mid-2015, 6-month warmup buffer).
- **Scan cadence:** weekly (every Monday), point-in-time.
- **Primary horizon:** **1 month (21 trading days).** Secondary (exploratory only): 1 week, 3 months.
- **Primary metric:** mean daily cross-sectional Spearman IC at the primary horizon.
- **Significance:** `moving_block_bootstrap` 95% CI on the per-date IC series + `date_level_significance`. (Each scan date = one independent unit.)

**Decision rule (the gate):**
- **PROCEED (forward-track):** primary-horizon mean IC bootstrap CI **excludes 0**, sign **positive**, and |mean IC| **≥ 0.02**. → build the conditional Phase (forward clock). *Caveat recorded: positive is inflated by survivorship → necessary, not sufficient; real money still gated on forward record + costs.*
- **KILL:** CI spans 0, or sign negative, or |mean IC| < 0.02. → divergence is **falsified on a sample biased in its favor**; stop building on it. Pivot honestly (research/monitoring tool; or test a different primary signal; or accept index investing).
- **Multiple-testing control:** ONE primary horizon, ONE signal config decide the gate. All other horizons/variants are exploratory and reported as such; they cannot flip the decision.

**LOCKED 2026-06-05 (user sign-off, before any result existed):**
1. **Primary horizon = 1 month (21 trading days).** 1w + 3m reported as exploratory only.
2. **Kill threshold = |mean IC| ≥ 0.02 with bootstrap CI excluding 0, positive sign.**
3. **Universe = broad ~605 (S&P 500 + NASDAQ-100)** for the gate. Thematic spine (27) returns as the forward-tracking universe in the conditional Phase if PROCEED.

These three are now frozen. No change after results.

---

## 5. Risks & pitfalls

1. **Survivorship inflation** — positive IC is overstated. Mitigated by treating the test as falsification-only; documented in the report.
2. **Researcher degrees of freedom** — controlled by Section 4 pre-registration; exploratory ≠ gate.
3. **Look-ahead** — attention by observation date; price ≤ T; forward returns strictly after T. Reuse sub-project B provenance guarantees + `LookAheadBiasError`.
4. **Weekly-attention boundary** (if Trends ever used) — excluded from primary to avoid it.
5. **Wikipedia article-mapping errors** (wrong page for a ticker) → noise; use the `themes.yaml` alias map where available, fall back to ticker, log misses.
6. **Thin cross-sections early in sample** — require ≥ N names with valid signal per date (e.g. ≥ 50) for a date to count.
7. **Conditional Phase only runs if the gate passes** — no building surfacing logic on a falsified signal.

---

## 6. Acceptance criteria (v1)

- Wikipedia attention backfilled for the broad universe (report coverage: names × date span).
- `compute_cross_sectional_ic` + `DivergenceICBacktestUseCase` implemented, unit-tested with fakes (no live APIs in tests).
- `validate-divergence-ic` CLI produces a pre-registered report: mean IC (primary + secondary), bootstrap CI, date-level significance, decile monotonicity, n_dates, n_names/date.
- A written **verdict**: PROCEED or KILL per Section 4, recorded in an ADR (ADR-044).
- If PROCEED: divergence-led surfacing + daily loop scheduled; outcomes sliced by divergence bucket.
- `make check` green, mypy strict, ≥90% coverage; merged feature → develop → main, green CI.
- **Not required:** real-money deployment, proven edge (forward record is months out), two-pillar (shelved).

---

## 7. Docs

- **ADR-044:** the pre-registered divergence-IC result + verdict (PROCEED/KILL) and what it means for the project's direction.
- Update CLAUDE.md status + CONTEXT.md glossary (cross-sectional IC, falsification-vs-validation, forward clock).
- Sub-project C (two-pillar) remains shelved behind this gate; note in its spec.

---

## 8. What this does NOT promise

It does not promise edge, and it cannot greenlight real money. Best realistic outcomes: (a) a small surviving IC → months of forward-tracking → possibly a tiny, risk-controlled deployment; or (b) a clean KILL that saves your capital and keeps you in index funds. Both are successful, honest outcomes.
