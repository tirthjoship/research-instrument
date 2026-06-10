# Design Spec — Unit B: Sub-$1B Non-Routine Insider-Cluster IC Falsification

**Date:** 2026-06-09
**Status:** Pre-registration (thresholds LOCKED before any data run)
**ADR:** ADR-052 (Unit B), builds on ADR-039/048/049/050/051 (falsification + IC + gate ethos)
**Branch:** `feat/insider-cluster-falsification`

> **This is a pre-registration document.** Every threshold, window, and decision rule
> below is fixed BEFORE the falsification is run. No threshold may be changed after
> seeing results (ADR-051 anti-p-hacking discipline). If the design proves infeasible
> on the data, the response is to widen confidence intervals / report INCONCLUSIVE —
> never to retune toward a PASS.

## 1. Purpose & hypothesis

The last sanctioned predictive swing (ADR-052). Six prior pre-registered falsifications
killed retail predictive alpha from public signals. This tests the **one idea with a
structural non-arbitrage argument**: institutions cannot fit into ~$300M names, so a
retail-size investor has a real execution advantage there.

**Pre-registered hypothesis (H1):** In the least-liquid tercile, clusters of non-routine
open-market insider buying carry **tradeable** 21-day forward information that survives
micro-cap slippage.

**Null (H0):** No such tradeable edge — rank-IC ≤ 0 and/or slippage-net spread ≤ 0.

**Expected outcome:** KILL (ADR-052 states low odds). The value of this Unit is
**closure**, not profit: a KILL takes prediction permanently off the table; a PASS would
be the first surviving predictive edge in the project and would still ship RESEARCH_ONLY
until independently re-validated.

**Effort posture:** LOW build, MAX verify. The danger is a **false positive**, not build
difficulty. Build effort is bounded; verification effort is not.

## 2. Signal definition (strict cluster)

A qualifying cluster signal for ticker `T` fires on date `d` when, within the 30 calendar
days ending on `d`:

- **≥ 3 distinct insiders** (distinct `RPTOWNERCIK`)
- each with **≥ 1 open-market purchase**, defined as both:
  - `TRANS_CODE = 'P'` (open-market purchase), AND
  - `TRANS_ACQUIRED_DISP_CD = 'A'` (acquired) with `TRANS_SHARES > 0`
- NB: `TRANS_CODE` and `TRANS_ACQUIRED_DISP_CD` are two different columns that both
  happen to use the letter `A`. We require code `P` and disposition `A` together.

**Excluded** `TRANS_CODE` values (never count toward the cluster):

- `S` (sale), `M` (option/derivative exercise), `A` (grant/award — the *code*, distinct
  from the acquired *flag* above), `G` (gift), `F` (tax withholding), `C`, `W`
- all derivative-table transactions (this signal is non-derivative only)
- any transaction flagged `EQUITY_SWAP_INVOLVED = true`
- **10b5-1 planned trades** where the dataset marks them (see §7 caveat — historical
  10b5-1 flagging is incomplete; documented, not silently ignored)

**Point-in-time rule (look-ahead safe):** the signal fires on the **filing date**
(`FILING_DATE` from the SUBMISSION table), NOT the transaction date. A cluster is only
"known" once all three Form-4s are publicly filed. `validate_point_in_time_access()`
(domain/services.py) and the `LookAheadBiasError` guard apply: no transaction with
`FILING_DATE > d` may contribute to the signal at `d`.

**Signal value:** binary cluster-fired indicator per (ticker, date). The rank-IC then
correlates the cluster event against forward return; the economic leg forms an
equal-weight basket of cluster names. (A continuous intensity score is explicitly out of
scope — keeps the pre-registered surface minimal; see ADR-052 strict-cluster choice.)

## 3. Data sources

| Need | Source | Notes |
|------|--------|-------|
| Insider transactions (historical) | **SEC DERA "Insider Transactions" (Form 345) quarterly flat files**, 2006Q1→latest | New ingest adapter. SUBMISSION (accession, filing date), REPORTINGOWNER (insider CIK, role), NONDERIV_TRANS (TRANS_CODE, TRANS_SHARES, TRANS_PRICEPERSHARE, TRANS_ACQUIRED_DISP_CD, EQUITY_SWAP_INVOLVED) |
| Forward 21d returns | yfinance | delisting-aware; unresolved names recorded, not dropped (§5) |
| Liquidity tercile split | yfinance price × volume (ADV) | point-in-time; **ADV proxy replaces market cap** (§7 Caveat 1) |
| IC / bootstrap / gate | **existing** `application/ic_analysis.py`, `screen_backtest_use_case.py`, `precision_metrics.py` | reuse |

The live EFTS `sec_edgar_adapter.py` is **untouched** — it is a full-text-search wrapper
(no transaction-code/shares/identity parsing; `transaction_value` hardcoded 0.0) and is
unsuitable for this backtest. New historical adapter: `sec_form345_dataset_adapter.py`.

## 4. Pre-registered two-leg gate (LOCKED)

Run the full evaluation **within each liquidity tercile**. The **primary test is the
bottom (least-liquid) tercile**; mid/top terciles are descriptive only (they demonstrate
cap/liquidity-dependence, they cannot move the verdict).

Horizon: **21 trading days**, single gate (no multi-horizon p-hacking surface).

**Leg 1 — information content:**
- Spearman rank-IC between cluster-fired indicator and forward-21d return
- **PASS Leg 1 iff:** `point_IC ≥ 0.02` AND `bootstrap_CI_lower_95 > 0`

**Leg 2 — tradeability (net of slippage):**
- Equal-weight basket of cluster names each period, held 21 trading days
- Spread = basket return − tercile-matched universe-mean return
- **Charged per-name round-trip slippage by tercile (pre-registered, bps):**
  - bottom (micro / least-liquid): **150**
  - mid: **75**
  - top (most-liquid): **40**
- **PASS Leg 2 iff:** slippage-net spread `bootstrap_CI_lower_95 > 0`

**Verdict combination (bottom tercile):**

| Leg 1 | Leg 2 | Verdict |
|-------|-------|---------|
| PASS | PASS | **PASS** → RESEARCH_ONLY edge, requires independent re-validation before any use |
| PASS | FAIL | **INCONCLUSIVE** (real information, not tradeable after micro-cap costs) |
| FAIL | PASS | **INCONCLUSIVE** (tradeable artifact without info content — treat with suspicion) |
| FAIL | FAIL | **KILL** → prediction permanently off the table (ADR-052) |

Bootstrap: reuse existing harness, **1000 resamples, 95% CI**.

## 5. Survivorship / coverage guard (LOCKED)

Delisting-aware returns: a cluster name that delists inside the 21-day window uses its
actual last-traded return (−100% if it goes to zero/bankrupt). Names with **no obtainable
forward price** are recorded as **`unresolved`** — **never silently dropped**.

**Coverage guard (overrides the gate):** if resolved forward-return coverage
`< 80%` of qualifying cluster events in the bottom tercile, the verdict is
**`INCONCLUSIVE_THIN_COVERAGE`** regardless of Leg 1 / Leg 2. This prevents residual
survivorship from manufacturing a PASS. The unresolved fraction is reported in every run.

## 6. Power guard (LOCKED)

Micro-cap clusters are rare. If the bottom tercile has **< 100 qualifying cluster events**
over the full sample, the verdict is **`INCONCLUSIVE_THIN_N`** — we do not KILL on sample
size, and we do not PASS on a handful of events. (100 chosen pre-data as a minimum for a
stable Spearman IC + bootstrap; documented, fixed.)

## 7. Known caveats (deliberate, documented deviations)

**Caveat 1 — liquidity (ADV) tercile replaces market-cap tercile.** True point-in-time
market cap requires shares-outstanding *history*; yfinance exposes only current shares →
look-ahead. We split on **ADV (price × volume), fully point-in-time**. This is arguably
*truer* to the structural thesis (liquidity, not cap, is what blocks institutional
participation) and removes a leakage vector. This is a conscious deviation from ADR-052's
"market-cap tercile" wording, approved 2026-06-09.

**Caveat 2 — residual survivorship from free data.** yfinance frequently lacks history
for delisted names, so "delisting-aware" is not fully guaranteed by the data. Mitigated by
the §5 coverage guard, which downgrades to INCONCLUSIVE rather than trust a thin-coverage
result. The residual gap is a reported number, not a hidden assumption.

**Caveat 3 — 10b5-1 historical flagging is incomplete.** The DERA datasets do not cleanly
flag 10b5-1 plans across all years. Where flagged, excluded; where not, included. This
slightly *weakens* the "non-routine" purity in a direction that, if anything, *adds noise*
(harder to PASS), so it does not bias toward a false positive. Documented.

## 8. Architecture (hexagonal — extend, don't rebuild)

- **adapters/data/** `sec_form345_dataset_adapter.py` (new) — download + parse DERA
  quarterly flat files → transaction records. Implements an insider-transactions port.
  yfinance forward-return + ADV via existing yfinance adapter.
- **domain/** insider-cluster detection (pure: given transactions + as-of date → cluster
  events), tercile assignment, slippage schedule. Zero framework imports. Reuses
  point-in-time validation services.
- **application/** `insider_cluster_falsification_use_case.py` — orchestrates: load
  transactions → detect clusters PIT → assign ADV terciles → compute forward returns
  (with unresolved tracking) → run Leg 1 (reuse `ic_analysis`) + Leg 2 (reuse
  `screen_backtest_use_case` / `precision_metrics` bootstrap) → apply coverage + power
  guards → emit verdict.
- **CLI:** `backtest-insider-clusters` — masked stdout (ADR-047), full-distribution report
  to `data/reports/insider_cluster_falsification_<date>.json` (a curated, tracked report).

## 9. Testing

- Pure-domain cluster detection, tercile, slippage: property-based (Hypothesis) +
  fixtures. Invariants: filing-date PIT never leaks; excluded codes never count; cluster
  requires ≥3 distinct CIKs.
- Use-case: small synthetic transaction + price fixtures (never the full DERA dump in
  pytest, never live yfinance in CI — project rule).
- Gate math: deterministic fixtures with known IC / known spread → assert exact verdict
  for each cell of the §4 table + both guards (§5, §6).
- Coverage target: ≥ 90% (project gate).

## 10. Out of scope (YAGNI)

- Continuous cluster-intensity scoring (binary cluster only).
- Multi-horizon gates (21d only).
- Sell-side / short signals (buys only).
- Any live/production surfacing — this Unit produces a verdict, not a feature. Surfacing
  is PASS-gated and would be a separate, separately-validated effort.
- Derivative-table transactions, 13D activist signals (separate existing path).

## 11. Verdict semantics recap

`PASS` (RESEARCH_ONLY) · `KILL` (prediction permanently off, ADR-052) · `INCONCLUSIVE`
(split legs) · `INCONCLUSIVE_THIN_COVERAGE` (§5) · `INCONCLUSIVE_THIN_N` (§6). The verdict
and full distribution are written to a tracked report and recorded in a new ADR on
completion.
