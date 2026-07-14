# Runbook: the Lazy Prices hypothesis

> A from-scratch orientation. Read this if you're picking up the Lazy Prices work and don't
> already carry the whole repo in your head. It explains **what** we're testing, **why**, **how**
> the machinery fits together, and the **exact process** to take it to a verdict — in that order.
>
> Quick-reference register: [`docs/HYPOTHESIS_BACKLOG.md`](../HYPOTHESIS_BACKLOG.md) ·
> Locked rules: [`docs/adr/057-lazy-prices-textchange-preregistration.md`](../adr/057-lazy-prices-textchange-preregistration.md) ·
> Code map: [`docs/ARCHITECTURE.md`](../ARCHITECTURE.md)

---

## 1. What this is, in plain English

Companies file 10-K (annual) and 10-Q (quarterly) reports with the SEC. Most of the text is
boilerplate that barely changes year to year. The **Lazy Prices** hypothesis (Cohen, Malloy &
Nguyen, *Journal of Finance*, 2020) is: when a company **materially rewrites** sections of its
filing — risk factors, legal proceedings, management discussion — that change tends to precede
**under-performance**. Companies that leave the language alone ("non-changers") tend to
**out-perform**. The market is slow to read the fine print, so the signal plays out over
*months*, not days.

We are **testing whether this holds out-of-sample (2015–2024)**, on liquid US large-caps, under
our own transaction-cost and statistical-significance bars. We are not claiming it works. The
output is a **verdict** (PASS / INCONCLUSIVE / HALT), recorded honestly either way.

## 2. Why we're testing *this* one (the chain of thought)

We have already pre-registered and **killed seven** prior alpha ideas (conviction, sentiment
divergence, insider clusters, momentum-exits, …). The lesson from those kills:

- A confidence interval that **spans zero** killed 6 of 7 — so we need a genuinely large effect
  and many independent observations.
- **Transaction costs** killed real gross signals — so we want a **slow, low-turnover** signal.
- **Coverage / survivorship** problems killed others — so we stay on a liquid universe.

Lazy Prices is attractive precisely because it dodges those failure modes:
1. It is an **independent information channel** — filing *language*, not price/sentiment/analyst
   data. Independent signals are what actually add value when combined (Fundamental Law of Active
   Management).
2. It is **slow-moving and low-turnover** (quarterly), so costs don't eat it alive.
3. The data is **free and point-in-time** — SEC filings are public with exact timestamps.

**Honest ceiling, stated up front:** the paper's sample ends in 2014. Published anomalies decay
~58% after publication (McLean–Pontiff). So even if it survives, expect single-digit annual gross,
and a PASS only earns the right to *forward-track* — never a claim of alpha.

## 3. How the test works (the machinery, without needing to read the code)

The core is one object, `LazyPricesBacktestUseCase`
([`application/lazy_prices_backtest.py`](../../application/lazy_prices_backtest.py)). It stays
"pure" — it doesn't know about the SEC, yfinance, or files. Instead you **inject three functions**
("callables"), and it orchestrates them. Think of it as an engine with three fuel lines:

| Callable you inject | Plain-English job | Returns |
|---|---|---|
| `similarity_fn(ticker, date)` | "How similar is this company's latest filing to its prior comparable one, as of this date?" | a number 0–1 (high = non-changer), or `None` if we can't compute it |
| `forward_return_fn(ticker, date)` | "What was this stock's return **minus the S&P 500** over the next 63 trading days?" | a number (the *excess* return) |
| `universe_fn(date)` | "Which tickers are in our universe on this date?" | a list of tickers |

The engine then, for each quarter ("cohort") from 2015 to 2024:
1. asks `universe_fn` who's in the universe,
2. computes everyone's `similarity_fn` and `forward_return_fn`,
3. measures the cross-sectional **rank correlation** (the "IC") between similarity and forward
   return — i.e. *did higher-similarity names actually earn higher returns?*,
4. also simulates a **tradeable long/short basket net of costs**.

Finally it applies a **locked decision tree** (the gates) and emits a verdict. The gates were
fixed *before any data was seen* and **must not be tuned** — that's what makes it a real test and
not a fishing expedition. The exact numbers live in ADR-057; in words:

- **Primary gate:** the IC must be both economically meaningful (`mean_ic ≥ 0.02`) and
  statistically positive (its bootstrap confidence interval excludes zero).
- **Secondary gate:** the long/short basket must still be positive **after** 50bps/side costs.
- **Full PASS needs both.** Guard rails fire first: too little coverage, too few quarters, or too
  few observations → the verdict is deferred as INCONCLUSIVE rather than trusted.

## 4. Where each callable's "fuel" comes from (the wiring)

All of this is **built, on `develop`, and smoke-validated** against live data (§5 Stage 1). The
descriptions below are where each callable's data comes from.

- **`similarity_fn`** ← `adapters/data/sec_filing_text_adapter.py` pulls the filing text
  (`list_filings` finds filings filed on/before the date — *point-in-time safe*; `fetch_sections`
  extracts the informative sections, now **hardened** to handle real messy SEC HTML). Then
  `domain/filing_textchange_service.py` turns a filing-vs-prior-filing pair into the similarity
  number. *(Glue still to write: pick the right prior comparable filing for each cohort.)*
- **`forward_return_fn`** ← `application/price_returns.py` (`compute_forward_return`,
  `load_price_series` from yfinance, point-in-time safe). "Excess" = the stock's return minus
  SPY's over the same 63 days. This exact pattern already exists at
  `application/corroboration_resolver_use_case.py:67-69`. *(Small function to write.)*
- **`universe_fn`** ← `application/ticker_universe.py` loads the static 512-name S&P500 ∪
  NASDAQ-100 list from `config/tickers/*.txt`. **Universe decision (2026-06-27):** we use the
  *current* list on purpose — see §6. *(Trivial to wire.)*
- **ticker → CIK** (the SEC's numeric company id, needed to fetch filings) ← **not built yet**;
  build a small resolver over the SEC's public `company_tickers.json`.

## 5. The process to a verdict (step by step)

Stages 0–1 are ordinary engineering you can do freely. Stages 2–3 are the **supervised**,
**irreversible** part — do not run them solo.

- **Stage 0 — DONE.** Pre-registration (ADR-057), the backtest engine, the similarity service, and
  the hardened filing-text extraction are all on `develop` and tested.
- **Stage 1 — BUILD + SMOKE-VALIDATED: DONE (2026-06-27).** Landed on `develop`: the ticker→CIK
  resolver (`adapters/data/sec_cik_resolver.py`), the three callables + cohort/pairing helpers
  (`application/lazy_prices_runner.py`), and the `lazy-prices` CLI command
  (`application/cli/backtest_commands.py`) — wires the adapters, disk-caches filing text + filing
  history, writes the JSON report. Dry-run: `uv run python -m application.cli lazy-prices --limit 60`
  (SMOKE, stamped `smoke_limit`, **not** a verdict).
  - **A live 60-name smoke validated the whole pipe end-to-end** and caught two real-world issues,
    both fixed: (1) `list_filings` read only the SEC `recent` feed (~2–4 yrs) → 2015–2020 cohorts
    starved (coverage 63%, 14/40 cohorts); now paginates the full submission history + caches per
    CIK. (2) class-share tickers (BRK.B) needed yfinance's dash form (BRK-B). After the fixes the
    smoke clears all guards: **coverage 89.5%, 40/40 cohorts, verdict INCONCLUSIVE** (the full gate
    runs — it just doesn't hit PASS on a 60-name slice, as expected). The IC/basket numbers on a
    smoke are noise and are deliberately not interpreted (ADR-057: no peeking/tuning).
  - **→ The rig is methodologically complete and ready for the supervised full run (Stage 2).**
- **Stage 2 — ONE-TIME FETCH (supervised).** Run a cached download of ~512 names × ~40 quarterly
  filings. The SEC rate-limits to ~1 request/second, so this takes **hours**. Cache it on disk so
  the actual run is fast and repeatable. *Kick this off knowingly — it's a long network job.*
- **Stage 3 — RUN THE GATE ONCE (supervised).** Execute the backtest a single time. Write the
  result to `data/reports/lazy_prices_ic_63d_<date>.json`. **Do not re-run to get a nicer number,
  and do not touch the thresholds** — ADR-057 allows exactly one re-run and only to fix a genuine
  validity bug, with thresholds unchanged.
- **Stage 4 — RECORD THE VERDICT.** Write ADR-058 with the outcome, **whatever it is**. A null is a
  real, publishable result here (see §6). On a PASS, the next step is forward-tracking, not trading.

## 6. The discipline that keeps this honest (read before Stage 2)

- **Pre-registration is sacred.** The gates are locked. Tuning them after seeing results turns a
  test into a story. One validity-bug re-run only.
- **Why a "null" is a *good* outcome.** We deliberately use the *current* 512-name universe, which
  is **survivorship-biased** — today's list is the companies that survived, which tilts the test
  *toward* finding an edge. So if it still comes back null, that's a **strong** null. If it comes
  back PASS, treat it as *weak* until confirmed on a point-in-time universe — survivorship could be
  doing the work. This is a conscious trade: cheapest honest test now, stronger confirmation later.
- **Point-in-time everywhere.** Every piece of data used to make a prediction must be timestamped
  on or before the prediction date. The adapters already enforce this; don't bypass it.
- **No imputation.** If a filing pair or price is missing, the observation is **dropped** and
  counted against coverage — never filled with a guess.

## 7. Pointers (where everything lives)

| You want… | Look at |
|---|---|
| The locked rules / exact thresholds | `docs/adr/057-lazy-prices-textchange-preregistration.md` |
| The quick-reference status | `docs/HYPOTHESIS_BACKLOG.md` → "Active hypotheses" |
| The backtest engine + gates | `application/lazy_prices_backtest.py` |
| The similarity math | `domain/filing_textchange_service.py` |
| Filing-text fetch + extraction | `adapters/data/sec_filing_text_adapter.py` |
| Prices / forward returns | `application/price_returns.py` |
| The universe list | `config/tickers/sp500.txt`, `config/tickers/nasdaq100.txt` |
| The detailed wiring research | `research/2026-06-27-lazy-prices-verdict-run-wiring.md` (local scratch) |

## Glossary

- **Cohort** — one quarterly snapshot date at which we measure the signal and look forward.
- **IC (information coefficient)** — the cross-sectional rank correlation between the signal and
  the forward return; positive = the signal ranked stocks correctly.
- **Excess return** — a stock's return minus the benchmark's (here SPY) over the same window.
- **Point-in-time** — using only information that was actually available on the date in question
  (no peeking at the future).
- **Survivorship bias** — testing only on companies that still exist today, which flatters results
  because the failures dropped out.
- **Long/short net-of-cost** — a simulated portfolio long the top names / short the bottom names,
  after subtracting trading costs; the test of whether the signal is *tradeable*, not just real.
