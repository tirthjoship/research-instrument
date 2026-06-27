# Hypothesis Backlog — the hunt stays disciplined, not dead

> ADR-052 closed backtest-driven alpha hunting permanently. This backlog is the ONLY
> sanctioned path for future predictive ideas: an idea may graduate to code ONLY
> after every field below is filled in and committed BEFORE any data is examined.
> Forward evidence (gate, adherence, screen IC) accrues regardless — read it before
> proposing anything here.

## Entry bar (all fields mandatory, committed before code)

| Field | Requirement |
|---|---|
| Hypothesis | One falsifiable sentence ("X predicts Y over horizon H") |
| Pre-registered thresholds | Exact pass/fail numbers, locked in an ADR |
| Kill condition | What result kills it permanently (no re-runs, no tuning) |
| Data cost | Sources, fetch budget, point-in-time feasibility |
| Conflict check | Must not violate ADR-052 scope or wrap-plan §5 (no online learning) |

## Active hypotheses

### Lazy Prices — SEC filing text-change (ADR-057)
> **New here? Read the runbook first:** [`docs/runbooks/lazy-prices.md`](runbooks/lazy-prices.md) —
> the from-scratch chain of thought + step-by-step process. This entry is the terse register.

- **Hypothesis:** higher inter-filing text similarity (a "non-changer") predicts a higher forward
  EXCESS return cross-sectionally over a 63-day (one-quarter) horizon.
- **Pre-registered thresholds (LOCKED, ADR-057):** primary rank-IC `ic_ci_low > 0 AND mean_ic ≥ 0.02`;
  secondary net-of-50bps long-short `ls_net_ci_low > 0`; full PASS needs BOTH. Guards: coverage ≥ 0.80,
  ≥ 20 cohorts, ≥ 1000 events. 8yr OOS (2015–2024), quarterly cohorts.
- **Kill condition:** `ic_ci_high < 0` → HALT_NEGATIVE; short of both gates → INCONCLUSIVE. No re-runs,
  no tuning (one validity-bug re-run allowed, thresholds unchanged).
- **Data cost:** SEC EDGAR filing text (free, point-in-time) + yfinance prices. One-time historical
  fetch ≈ 512 names × ~40 quarterly filings @ 1 req/s ≈ hours; cached so the gate run is fast/re-runnable.
- **Universe decision (2026-06-27):** static current 512-name S&P500 ∪ NASDAQ-100 snapshot
  (`config/tickers/*.txt`) — survivor-biased ON PURPOSE per ADR-057 (bias favours finding an edge, so a
  null is the stronger conclusion; a PASS would need a point-in-time follow-up before belief).
- **Conflict check:** distinct channel (filing linguistics), a NEW pre-registered hypothesis — not a
  backtest re-run of a killed signal; within ADR-052 scope.

**Rig + wiring (promoted from `research/2026-06-27-lazy-prices-verdict-run-wiring.md` so we don't re-research):**
- Use case `application/lazy_prices_backtest.py` — injected callables `similarity_fn` /
  `forward_return_fn` (excess vs SPY) / `universe_fn`; verdict tree LOCKED.
- Signal `domain/filing_textchange_service.py::textchange_similarity` (None = drop, never impute).
- Filing text `adapters/data/sec_filing_text_adapter.py` — `list_filings(ticker, cik, as_of)` (PIT) +
  `fetch_sections` (HARDENED 2026-06-27: bs4/lxml, inline-XBRL unwrap, TOC-defeating item splitter).
- Reuse for the callables: `forward_return_fn` = `compute_forward_return(ticker,t,63) −
  compute_forward_return(SPY,t,63)` (`application/price_returns.py`; pattern lives at
  `application/corroboration_resolver_use_case.py:67-69`). `universe_fn` = the static loader
  `application/ticker_universe.py`. ticker→CIK = SEC `company_tickers.json` resolver (TO BUILD).
- Runner: a `lazy-prices` CLI command modelled on `application/cli/backtest_commands.py` (inline adapter
  wiring + price cache, quarterly cohort gen, report → `data/reports/lazy_prices_ic_63d_<date>.json`).
- **Status (2026-06-27):** rig + hardened extraction + the full runner (ticker→CIK resolver, the
  three wiring callables, the `lazy-prices` CLI command with disk-cached fetch) all landed on
  develop. Dry-runnable now via `lazy-prices --limit 60` (smoke, not a verdict). Remaining: the
  one-time live historical fetch + ONE gate run (supervised) → write the verdict ADR-058.

## Parked ideas

### Unit D — realized-slippage measurement (parked by wrap plan §6)
- **Hypothesis:** realized execution cost on sub-$1B names is materially below the
  assumed 150 bps, enough to flip Unit B's net verdict.
- **Preconditions if ever revived:** Unit B INCONCLUSIVE with gross CI_low > 0
  (NOT met — final verdict was INCONCLUSIVE_THIN_COVERAGE → practical KILL);
  pre-registered order budget and plan; measured cost < gross edge required.
- **Status:** PARKED. Preconditions currently fail — listed for honesty, not intent.

### Correlation-vs-book fit input (deferred from fit verdict, 2026-06-11)
- **Hypothesis:** none — this is descriptive arithmetic (pairwise return correlation
  of a candidate vs current holdings), not a predictive claim.
- **Why parked:** medium build cost vs weekend wrap deadline; needs price-history
  fan-out per holding.
- **Entry path:** ordinary feature work post-wrap (no pre-registration needed —
  descriptive), budgeted under the ~1 hr/quarter maintenance allowance.
