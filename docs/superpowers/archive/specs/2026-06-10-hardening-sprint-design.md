# Hardening Sprint — Resilient Fetch, Fail-Loud, Delisted Prune, Green `make check`

**Date:** 2026-06-10 · **Status:** Approved (brainstorm complete)
**Parent:** Strategic wrap plan §5 (self-sustainability), build-week item 4.
**Branch:** `feat/hardening-sprint` (stacked on `feat/unit-c-adherence`; rebase onto
develop after Unit C / PR #37 merges).

## Purpose

Make `make check` green and make the zero-touch Saturday job **never silently
emit garbage** (wrap plan §5: "any data-fetch failure is reported loudly; the
job never silently emits garbage. Auto-prune delisted tickers. Retry/backoff on
all external fetches"). Maintenance budget target: ~1 hr/quarter.

## Root cause found

- Active venv is the **workspace-level** `/Users/tirthjoshi/My Data Science
  Projects/.venv` (Python 3.13.7), shared across all 3 projects. This project's
  pyproject.toml declares `feedparser, networkx, plotly, streamlit, praw` but
  they are NOT installed there → 55 test failures + 5 collection errors, all
  `ModuleNotFoundError`. yfinance IS installed (prices work).
- `application/price_returns.py::load_price_series` wraps the whole fetch in
  `except Exception: return []` — a real fetch failure is indistinguishable from
  a genuinely-empty series. This is the silent-failure the sprint targets.

## Decisions (locked during brainstorm)

| Question | Decision |
|---|---|
| Venv drift | **Install into shared `.venv`** — `pip install -e .` so pyproject is the verified source of truth. Additive deps, no version conflicts observed. |
| Fail-loud | **Tri-state fetch** — data / no-data (`[]`) / error (raise `PriceFetchError`). Distinguish empty from failed. |
| Retry | **Hand-rolled** exponential backoff in the yfinance adapter, stdlib only, injectable sleep for tests. No new dependency. |
| Delisted | **Log + skip + persist** a gitignored prune-list; auto-skip on future runs; reversible by editing the file. |
| Caller safety | `load_price_series` keeps `[]`-on-error as DEFAULT; gains `strict: bool = False`. Only weekly-job paths opt into `strict=True`. Zero breakage to ~18 existing callers. |

## Architecture — 4 loosely-coupled units

The shared concept is a **tri-state fetch result**: `data` | `no-data` | `error`.
That tri-state is what lets fail-loud, delisted-prune, and health-check stay
clean and independent.

### Unit 1 — Venv reconcile (ops, no code)
- `pip install -e .` into the shared `.venv`; confirm every pyproject dep
  imports; `make check` runs end-to-end.
- Acceptance: `python -c "import feedparser, networkx, plotly, streamlit, praw"`
  succeeds; `make test` collection errors → 0; the previously-failing 55 tests
  pass or reveal genuine (non-import) failures to triage separately.
- NOT in scope: changing pyproject deps, pinning versions, mypy config.

### Unit 2 — Resilient fetch (retry/backoff + typed error)
- New `domain/exceptions.py::PriceFetchError` (domain stays pure — it already
  hosts `LookAheadBiasError`).
- New stdlib retry helper. Location: `adapters/data/retry.py`
  `retry_with_backoff(fn, *, attempts=3, base_delay=1.0, sleep=time.sleep,
  retryable=(Exception,))` — exponential `base_delay * 2**i`, re-raises the last
  exception after `attempts`. `sleep` injectable so tests use a fake clock (no
  real waiting).
- `adapters/data/yfinance_adapter.py`: wrap the low-level `yf.Ticker(...).history`
  call in `retry_with_backoff`. A transient network error retries; persistent
  failure raises. An empty DataFrame is NOT an error (no retry) — returns empty.
- `application/price_returns.py::load_price_series(ticker, start, end, *,
  strict=False)`:
  - empty df → `[]` (both modes). Empty is no-data, never an error — the holding
    may be too new or genuinely delisted (Unit 3 decides which over time).
  - exception after retries: `strict=False` → log warning + `[]` (current
    behavior, preserved for the ~18 callers); `strict=True` → raise
    `PriceFetchError(ticker, cause)`.
  - The weekly fetch loop (Unit 4) calls `strict=True` but catches the error
    per-ticker, so the raise is the loud SIGNAL, not a job-killer.
- Tests: fake fetch that fails N times then succeeds (assert retried, backoff
  delays requested via fake sleep); fake that always fails (strict raises;
  non-strict returns `[]`); empty df (no retry, `[]`).

### Unit 3 — Delisted prune
- New `application/delisted.py`:
  - `record_fetch_outcome(prune_state: dict, ticker, had_data: bool) -> dict` —
    pure: increments a consecutive-no-data counter, resets on data.
  - `is_delisted(prune_state, ticker, threshold=3) -> bool`.
  - `load_prune_list(path) / save_prune_list(path, state)` — JSON at gitignored
    `data/personal/delisted.json` `{ticker: consecutive_no_data_weeks}`.
- A ticker with `≥ threshold` (default 3) consecutive no-data weeks is logged
  loudly and skipped from assessment on subsequent runs. Reversible: delete its
  key (or the file) to retry. Threshold guards against a one-off yfinance hiccup
  pruning a live name.
- Pure counting logic is unit-tested; file I/O is thin.

### Unit 4 — Health check on the weekly job
- **Collect-then-fail, never abort mid-loop.** A 66-name run must NOT die on the
  first flaky fetch and lose the other 65 assessments. The fetch provider used
  by holdings-risk catches `PriceFetchError` per ticker, records the ticker into
  a failures list, and continues. After the loop: print a one-line health
  summary `fetched OK=<n> no-data=<n> FAILED=<n> pruned=<n>` (FAILED tickers
  named), then exit NON-ZERO if `FAILED > 0`. So the job is both complete (all
  fetchable names assessed) and loud (non-zero exit + named tickers).
- Distinction that makes this clean (tri-state): delisted/no-data names are `[]`,
  NOT errors — they land in `no-data`/`pruned`, never `FAILED`, never abort. Only
  genuine fetch errors (after retries) count as `FAILED`.
- `scripts/discipline_weekly_review.sh` runs under `set -euo pipefail`, so the
  non-zero exit fails the Saturday job loudly (visible in
  `discipline_weekly_review.log`); the summary line is captured above it.
- Implementation: a thin `application/fetch_health.py` health-tracking helper
  (pure counters: `record_ok/record_no_data/record_failed/record_pruned`,
  `summary_line()`, `any_failed()`) the fetch loop updates; commands read it to
  decide exit code. Keeps CLI commands thin and the logic unit-testable.
- Acceptance: a forced fetch failure on 1 of N names → the other N−1 are still
  assessed, summary shows `FAILED=1` with the ticker, job exits non-zero; a
  delisted name shows under `pruned`, not `FAILED`, and the job still exits 0 if
  no real errors.

## Caller-migration risk (explicit)

`load_price_series` is called in ~18 sites. The `strict` default of `False`
preserves today's `[]`-on-error contract everywhere; only the three weekly-job
fetch paths pass `strict=True`. No silent behavior change for backtests,
dashboards, or research scripts. The retry/backoff in the adapter benefits ALL
callers transparently (fewer transient `[]`).

## Testing

TDD. No real network in any test. Fake fetchers + injectable sleep. Hypothesis
for the prune counter invariant (data always resets the counter to 0; N no-data
weeks ⇒ counter == N). Unit 1 is verified by running the suite, not by a new
test. mypy strict on new modules. The existing 55 import-failures are the
acceptance signal for Unit 1 — they must go green (or reveal non-import issues).

## Out of scope

- Pinning dep versions / lockfile (separate concern).
- Migrating to a project-local venv (rejected: rewires make/cron/editor).
- Adding tenacity or any retry dependency.
- Caching changes (caches are sacred — untouched).
- Fixing the known `unrealized_pct` currency bug (post-gate decision).

## Sequencing note

Stacked on Unit C because Unit 4 edits the same Saturday script Unit C extended.
After PR #37 merges, rebase this branch onto develop (or merge Unit C first,
then branch). Unit 1 (venv) should land first — it gives the green baseline the
other three units' tests run against.
