# Personal Momentum & Exit-Discipline Backtest — Design Spec

**Date:** 2026-06-07
**Status:** Draft (pending user review)
**Author:** Tirth Joshi

## Why (the real problem)

Three independent falsification tests (ADR-039, ADR-043, ADR-044) killed the "predict winners from public sentiment/attention/conviction" thesis. The honest pivot, grounded in evidence and in the user's own trading history, is from **prediction** to **disciplined exit + risk management**.

The user's losses are not stock-selection failures — they are **timing/behavior failures**:
- **LULU:** bought $166 (fair value), rode to $210 (+27%), held to $114 (−31%) anchoring on the old $400 price. No exit rule + disposition effect.
- **MU:** sold $220, watched it run to $1000. A *fixed* profit cap is the wrong exit.
- **Current portfolio confirms the pattern:** winners are trend-intact momentum names held correctly (MU +863%, PLTR +447%, AMD +195%, …); the large losers are broken-trend names held against the trend (RIVN −56%, NKE −57%, SOUN −48%, LSPD −49%, FIGS −32%) — every one below its 200-day trend for months.

The asymmetry — *win by holding momentum, bleed by holding broken trends* — is the documented "let winners run, cut losers" effect. The average equity investor underperformed the S&P by **848 bps in 2024** purely from this behavior gap (Barclays/DALBAR). This study tests whether a pre-registered, rules-based discipline would have closed that gap — **before** any engine is built on it.

## Hypothesis under test (pre-registered)

> A simple, rules-based **trend filter + volatility-scaled trailing exit + relative-momentum selection**, applied to a broad equity universe over 2018–2026, produces **better risk-adjusted returns and materially lower drawdowns** than buy-and-hold-forever (the user's current behavior), out of sample.

This is **not** a claim of beating SPY by 20–30%. It is a claim of *better risk-adjusted* outcomes and *drawdown reduction* — the documented value of trend-following (AQR TSMOM; Antonacci dual momentum: 17.4%/yr vs 8.85%, max DD 22.7% vs 60% over 39 yrs).

## Pre-registered rules (LOCKED before any result — textbook defaults, NO tuning to the user's trades)

1. **Absolute-momentum trend filter:** hold a name only while `close > SMA(200)`. Below it → out (to cash). (Standard 200-day / 10-month trend filter.)
2. **Trailing exit (Chandelier):** stop = `highest_high_since_entry − 3 × ATR(22)`. Exit when close breaches the stop. Rides runners (MU), ejects breaks (LULU) — no fixed profit cap.
3. **Relative-momentum selection:** rank universe by **12-minus-1-month** total return (skip the most recent month). Eligible longs = top tercile that also pass the trend filter.
4. **Regime overlay (portfolio-level on/off):** scale equity exposure down when the broad index (SPX/TSX) is below its own SMA(200). (Reduces whipsaw exposure in bear regimes.)

Parameters (200, 3×ATR(22), 12-1, top tercile) are **frozen** in this spec. They are standard defaults from the literature, chosen *without reference to how they perform on the user's holdings*. No grid-search, no per-name tuning. If they underperform, that is an honest result, not a reason to re-tune.

## Backtest design (the validation — carries all statistical weight)

- **Universe:** US S&P 500 + NASDAQ-100 + Canadian TSX 60 (the user holds US large-cap tech + Canadian names SU, LSPD). Point-in-time membership where available; survivorship caveat recorded.
- **Period:** 2018-01-01 → 2026-06-01. Daily prices via yfinance (`.TO` suffix for TSX).
- **Strategy:** the four pre-registered rules, run as a **monthly-rebalanced long-only portfolio** with volatility-scaled position sizing (inverse 60-day realized vol, capped).
- **Baselines:**
  1. **Buy-and-hold-everything, equal-weight** (proxy for "hold forever" / disposition behavior).
  2. **SPY buy-and-hold** (the benchmark).
- **Metrics:** CAGR, **Sharpe**, **max drawdown**, Sortino, average give-back-from-peak avoided, turnover, hit rate, time-in-cash. Reported with **block-bootstrap CIs** (reuse `moving_block_bootstrap` from `precision_metrics`) and walk-forward / regime split (reuse `RegimeSplitter`, `DrawdownTracker`).
- **Look-ahead discipline:** all signals use data ≤ decision date (existing `validate_point_in_time_access`); `LookAheadBiasError` guards.

### LOCKED success criterion (pre-registered verdict gate)

**PROCEED** (build the engine) iff, out of sample across the broad universe, the strategy:
- beats buy-and-hold-everything on **Sharpe** (bootstrap CI on the Sharpe difference excludes 0), **AND**
- reduces **max drawdown by ≥ 30%** vs buy-and-hold-everything.

Raw CAGR may be *lower* than buy-and-hold in a bull-heavy window — that is expected and acceptable; the thesis is risk-adjusted improvement + drawdown reduction, reported honestly either way.

**KILL** → discipline-rules don't help out of sample either; stop, report honestly, do not build the engine. (Same falsification rigor as ADR-044.)

## Personal application layer (the "feel" — runs only AFTER backtest, applies the validated rules)

For each of the user's 20 current holdings, compute and tabulate **today's** rule output:
- price vs SMA(200) (trend status: intact / broken, and since when)
- current Chandelier trailing-stop level + distance to it
- 12-1 momentum percentile within the universe
- **verdict:** HOLD (trend intact, trailing) / TRIM (size/risk) / EXIT (trend broken) — with a one-line **why**

This is **application, not validation** — stated explicitly in the output. It is the actionable read on the user's real money; it does not prove anything by itself (n=20, outcome-selected).

## Phase 2 — Screener + Daily Decision Feed (CONDITIONAL on Phase-1 PROCEED)

> Builds ONLY if the Phase-1 backtest passes the locked success bar. If Phase 1 returns KILL, there is no validated rule set to recommend from, and Phase 2 does not exist. This is the same conditional discipline as ADR-044's Phase 5.

The user wants the engine to **surface new candidates** (not just manage held names), give **buy/sell/horizon** per name, and **update daily** — without false positives. The honest realization of that, gated on validated rules:

- **Candidate screener (SCREEN, not PREDICT):** rank the full US+TSX universe by the *same* pre-registered momentum/trend/quality filters. Output = "names currently meeting the criteria your winners shared," with entry zone, Chandelier exit, and momentum percentile. Framed explicitly as a **filter, never a forecast.** It would plausibly have surfaced MCK/WMT/COST/TXN/STN/HXL while they trended, and would ride IRDM/LUNR/ASTS/RKLB-type names **only once a confirmed uptrend exists** — never predicting them cold.
- **Dynamic horizon, not fixed:** "how long to hold" = "until the trend breaks" (the trailing stop defines it). Long-term for runners (MU-style), short for quick breaks. No fake fixed horizons.
- **Daily decision feed:** recompute trend status, trailing stops, and momentum rank for held names + screened candidates; surface only **state changes** (a holding broke trend → exit alert; a name entered the top tercile → new candidate). Reuses the existing daily-scan infra.
- **LLM as narrator, never picker:** news/broker-rating context is summarized by the LLM to explain *why* a name moved or what changed — it does **not** generate or rank picks (StockBench/KDD-2026: LLM agents predict badly, explain well). Analyst-rating *changes* (not levels) may appear as one context input, clearly labeled low-weight.
- **Calibrated, not confident:** every surfaced name carries an honest confidence and the engine **abstains** when signals are weak (extends ADR-039's abstention). No "strong buy" theater. The "no false positives" goal is reframed as **cheap false positives**: the trailing-stop discipline makes a wrong call exit fast and small — wrong cheaply, right big.

**The hard line:** "false-positive-free recommendation" is impossible and is explicitly NOT promised. The engine's value is the asymmetry (cut losers cheap, ride winners), not predictive accuracy. Any feature that would require predicting which name rises is out of scope — that is the falsified thesis.

## Honesty constraints (non-negotiable)

1. **Rules frozen before results** — no tuning to LULU/MU/the 20 holdings.
2. **Backtest validates; holdings apply** — never conflate them.
3. **Survivorship caveat** stated (current index membership; delisted names absent — biases *toward* finding edge).
4. **Bull-regime caveat** — 2018–2026 is mostly bull; trend-following's edge is largest in sustained bears (2000, 2008), so this window *understates* drawdown benefit. Note that 2025–26 shallow dips whipsawed momentum.
5. **No real-money auto-execution.** Output is decision-support; the user decides and trades.
6. **Privacy:** the user's actual holdings (tickers, share counts, cost basis) are personal financial data. They live in a **gitignored local file** (`data/personal/holdings.csv`), are NEVER committed, and never leave the machine. Specs/ADRs/commits reference at most a few tickers illustratively, never the full position list with sizes.

## Explicitly OUT of scope (YAGNI / avoid the hype the research flagged)

- No LLM/sentiment stock-picking (StockBench/KDD-2026: LLM agents underperform; our own ADR-044). LLM may *narrate the why* only, never select.
- No new sentiment/attention sources. (Attention as a contrarian overlay is a *possible future sleeve*, not this study.)
- No reinforcement learning / deep-learning predictor (overfits, regime-brittle).
- No intraday/scalping. Daily data, monthly rebalance.

## Reuse of existing components

`precision_metrics` (bootstrap, date-level significance), `RegimeSplitter`, `DrawdownTracker`, `TransactionCostModel`, yfinance adapter + caching, the point-in-time look-ahead guards, the SQLite store. Hexagonal: pure rule logic in `domain/`, backtest orchestration in `application/`, prices via the existing adapter. New: a `TrendExitRules` domain service + a `MomentumExitBacktestUseCase` + a `validate-momentum-discipline` CLI + a `portfolio-verdict` CLI for the personal layer.

## Risks / limitations

- Single-stock trend-following is noisier than cross-asset TSMOM; evidence weaker than asset-class momentum. Reported honestly.
- Transaction costs/taxes on higher turnover modeled via `TransactionCostModel`; taxes (the user is Canadian, likely TFSA/non-registered) noted but not fully modeled.
- A bull-heavy backtest window may under-credit the drawdown benefit (see caveat 4).
