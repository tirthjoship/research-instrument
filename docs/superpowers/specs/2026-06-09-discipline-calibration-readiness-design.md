# Discipline Calibration-Readiness Harness — Design

**Date:** 2026-06-09
**Status:** Approved (brainstorming)
**Builds on:** ADR-047 (discipline engine), ADR-048 (forward-calibration gate — LOCKED), ADR-050 (trend-following INCONCLUSIVE — discipline is the terminal bet)
**Amends:** the *experimental design* of ADR-048 (pre-outcome, thresholds unchanged) → ADR-051

## 1. Problem

The discipline REDUCE-flag forward gate (ADR-048) is the last live hypothesis with in-sample signal and the project's terminal bet. Its forward log (`data/personal/discipline_log.jsonl`) currently holds **132 rows all dated 2026-06-08** (46 REDUCE / 46 TRIM / 24 ADD_OK / 16 HOLD). Two failures threaten the gate:

1. **No automated logging.** No launchd job is loaded; the *documented* plist runs `daily-cycle` (the opportunity loop), which does **not** append discipline verdicts. Nothing feeds the gate.
2. **Single-date confound.** All REDUCE flags share one `as_of`, so they resolve over the *identical* market window. The pooled `down_rate_on_reduce` then rides on whether that one month fell broadly — not on whether the flags discriminate. A confounded PROCEED *or* KILL is equally worthless.

## 2. The methodological frame (non-negotiable honesty)

**ADR-048's thresholds stay exactly locked:** `down_rate_on_reduce ≥ 0.55` AND `brier ≤ 0.45` AND `n ≥ 30`, 21-calendar-day horizon. We change **none** of them.

Zero flags are resolved yet (earliest resolves ~2026-06-30; today is 2026-06-09). We are strengthening the **experimental design before any outcome is observable** — analogous to fixing a power/sample-design requirement before unblinding. The amendment **adds a pre-resolution validity precondition**: the REDUCE sample must span enough distinct `as_of` dates before the locked thresholds are evaluated.

**Anti-p-hacking protections, pre-committed in ADR-051:**
- The diversity guard blocks a confounded **PROCEED and a confounded KILL symmetrically**.
- The diversity threshold is fixed now (K=3 distinct dates, D=10 calendar-day spread), not tuned to observed down-rates.
- The gate **resolution date is fixed** (ADR-048's mid-late-July window). We do **not** extend collection to chase a result; whatever diverse sample exists at the resolution date is the sample.

If diversity is insufficient at the resolution date, the honest verdict is `INCONCLUSIVE_THIN_DATES` (the design failed to collect a clean sample), **not** a pass and **not** a kill.

## 3. Components

### A. Corrected daily logging cron

- Runs `python -m application.cli holdings-risk` **daily** (cheap: ~66-ticker yfinance batch), appending to `data/personal/discipline_log.jsonl`.
- ~3-week window (2026-06-09 → ~06-28) → ~20 distinct `as_of` dates, all resolvable before the gate. Daily chosen for simplicity + max coverage; moving-block bootstrap absorbs adjacent-day autocorrelation.
- Deliverables: `scripts/discipline_daily.sh` wrapper (cd to repo, venv python, append-log, stderr→logfile); corrected launchd plist in `docs/scheduling.md` (replaces the wrong `daily-cycle` example for this purpose); `caffeinate -i` / `pmset` guidance for the laptop-sleep caveat.
- Idempotency: multiple runs on the same calendar date are allowed (append-only); the readiness math dedupes on distinct `as_of` date.

### B. `discipline-calibration-status` CLI

Read-only over the same JSONL. Masked stdout (no tickers). Reports:
- counts by verdict;
- **distinct `as_of` dates** + calendar spread (min→max);
- REDUCE flags **resolvable now vs pending** against the 21-day horizon and today;
- **last-logged freshness** (days since most recent `as_of`) → surfaces a silently-dead cron;
- **readiness verdict**: `READY` (≥30 resolvable REDUCE across ≥3 dates / ≥10-day spread by projection) vs `THIN` with the specific shortfall and a projected n at the gate date.

### C. Date-diversity guard in `resolve-discipline-flags`

After `resolve_flags`, compute the `as_of` spread of the **resolved REDUCE** flags. Gate label:
- `n_resolved < 30` OR `distinct_dates < 3` OR `spread_days < 10` → **`INCONCLUSIVE_THIN_DATES`** (keep logging; thresholds not yet evaluable on clean data).
- else evaluate the **locked** ADR-048 thresholds → `PROCEED` (down-rate≥0.55 AND brier≤0.45) / `KILL` (otherwise).
- The existing informational down-rate / brier / TRIM lines still print verbatim; the guard only governs the **label**.

## 4. Architecture

- **New pure module** `application/calibration_readiness.py` — stdlib only, fully unit-testable on synthetic logged-row dicts (no network, no yfinance):
  - `as_of_spread(rows) -> {distinct_dates, span_days, min, max}`
  - `resolvable_split(rows, today, horizon_days) -> {resolvable, pending}` (REDUCE only)
  - `freshness(rows, today) -> days_since_last`
  - `readiness(rows, today, horizon_days, gate_date, k_dates, d_days, n_min) -> ReadinessReport` (frozen dataclass: verdict READY/THIN + shortfalls + projected_n)
  - `diversity_label(resolved_reduce_rows, down_rate, brier, k_dates, d_days, n_min) -> str` (the Component-C decision; pure, symmetric)
- **Modify** `application/cli.py` — add `discipline-calibration-status`; wrap the `resolve-discipline-flags` label with `diversity_label`. The resolve command keeps loading prices via the existing `load_price_series` provider; the new label needs only the resolved rows' `as_of` (already in the log) — pass the matched REDUCE rows through.
- **No domain/ change** — this is application-layer calibration bookkeeping, not a business rule. Keeps `domain/` pure (CLAUDE.md rule 1).
- Privacy: status + guard mask tickers on stdout (ADR-042 / ADR-047 convention); the JSONL stays gitignored under `data/personal/`.

## 5. Testing

`tests/test_calibration_readiness.py` (pure, synthetic rows, no network):
- `as_of_spread`: single-date → span 0 / distinct 1; multi-date → correct span + count; dedupes same-date rows.
- `resolvable_split`: flags older than horizon = resolvable; newer = pending; boundary at exactly horizon.
- `freshness`: days-since-last; empty log handled.
- `readiness`: 1 date many flags → THIN (distinct<3) even if n≥30; 3 dates ≥10-day spread ≥30 flags → READY; projection counts pending-but-will-resolve-by-gate.
- `diversity_label` **symmetry**: confounded high down-rate (1 date) → `INCONCLUSIVE_THIN_DATES` (not PROCEED); confounded low down-rate (1 date) → `INCONCLUSIVE_THIN_DATES` (not KILL); diverse + pass thresholds → PROCEED; diverse + fail → KILL.
- A CLI smoke test for `discipline-calibration-status` on a synthetic tmp log (monkeypatch the log path), assert masked output + verdict string present.

`make check` green, ≥90% coverage on the new module (it is pure → trivially coverable).

## 6. ADR-051

Records: the single-date confound found 2026-06-09; the pre-outcome design amendment (diversity precondition, thresholds unchanged); the K/D/n_min values; the anti-p-hacking protections (symmetric guard, fixed threshold, fixed resolution date, no collection-extension); and that an insufficient-diversity outcome at the gate = `INCONCLUSIVE_THIN_DATES` (an honest design failure, not a result).

## 7. Out of scope (YAGNI)

- No dashboard tab (CLI status is enough for a personal tool; can add later).
- No change to the discipline scorer, verdict logic, or ADR-048 thresholds.
- No backfill of historical as_of dates (would be look-ahead-adjacent fabrication; forward data must accrue honestly).
- The cron does not auto-resolve or auto-decide the gate — resolution stays a deliberate user-run at the fixed date.
