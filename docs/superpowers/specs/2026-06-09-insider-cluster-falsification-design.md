# Design Spec — Unit B: Sub-$1B Non-Routine Insider-Cluster IC Falsification

**Date:** 2026-06-09
**Status:** Pre-registration (thresholds LOCKED before any data run)
**ADR:** ADR-052 (Unit B), builds on ADR-039/048/049/050/051 (falsification + IC + gate ethos)
**Branch:** `feat/insider-cluster-falsification`
**Feasibility:** VERIFIED 2026-06-09 (see §3.1) — DERA dataset, columns, coverage floor,
and IC/bootstrap reuse surface all confirmed against live sources before planning.

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

**Signal value:** binary cluster-fired indicator per (ticker, fire_date). Each fired event
becomes one observation whose **abnormal return** (vs a liquidity-matched benchmark, §4)
feeds the gate. (A continuous intensity score is explicitly out of scope — keeps the
pre-registered surface minimal; see ADR-052 strict-cluster choice.)

## 3. Data sources

| Need | Source | Notes |
|------|--------|-------|
| Insider transactions (historical) | **SEC DERA "Insider Transactions" (Form 345) quarterly flat files**, 2006Q1→latest | New ingest adapter. SUBMISSION (accession, filing date), REPORTINGOWNER (insider CIK, role), NONDERIV_TRANS (TRANS_CODE, TRANS_SHARES, TRANS_PRICEPERSHARE, TRANS_ACQUIRED_DISP_CD, EQUITY_SWAP_INVOLVED) |
| Forward 21d returns | yfinance | delisting-aware; unresolved names recorded, not dropped (§5) |
| Benchmark 21d returns | yfinance ETFs `IWC` (bottom), `IWM` (mid/top) | market-adjusted abnormal return, beta=1 (§4) |
| Liquidity tercile split | yfinance price × volume (ADV) | point-in-time; **ADV proxy replaces market cap** (§7 Caveat 1) |
| IC / bootstrap / gate | **existing** `application/ic_analysis.py`, `screen_backtest_use_case.py`, `precision_metrics.py` | reuse |

The live EFTS `sec_edgar_adapter.py` is **untouched** — it is a full-text-search wrapper
(no transaction-code/shares/identity parsing; `transaction_value` hardcoded 0.0) and is
unsuitable for this backtest. New historical adapter: `sec_form345_dataset_adapter.py`.

### 3.1 Verified data facts (checked 2026-06-09, live)

- **File URL pattern (HTTP 200):**
  `https://www.sec.gov/files/structureddata/data/insider-transactions-data-sets/{YYYY}q{Q}_form345.zip`
- **SEC fair-access:** requests MUST send a declared `User-Agent` (contact string) or
  the server returns 403. The adapter sets one.
- **Coverage floor: 2006q1** (2005 and earlier → 404). Sample window = 2006q1 → latest.
- **Tables present:** SUBMISSION, REPORTINGOWNER, NONDERIV_TRANS, DERIV_TRANS,
  NONDERIV_HOLDING, DERIV_HOLDING, FOOTNOTES, OWNER_SIGNATURE (TSV) + `FORM_345_readme.htm`.
- **Verified columns used by this design:**
  - SUBMISSION: `ACCESSION_NUMBER`, `FILING_DATE`, `ISSUERTRADINGSYMBOL` (ticker — no
    CIK→ticker lookup needed), `ISSUERCIK`, `PERIOD_OF_REPORT`, **`AFF10B5ONE`** (10b5-1
    affirmation flag)
  - REPORTINGOWNER: `ACCESSION_NUMBER`, `RPTOWNERCIK` (distinct-insider key),
    `RPTOWNER_RELATIONSHIP`, `RPTOWNER_TITLE`
  - NONDERIV_TRANS: `ACCESSION_NUMBER`, `TRANS_CODE`, `TRANS_ACQUIRED_DISP_CD`,
    `TRANS_SHARES`, `TRANS_PRICEPERSHARE`, `EQUITY_SWAP_INVOLVED`, `TRANS_DATE`,
    `DIRECT_INDIRECT_OWNERSHIP`
- **Join keys:** SUBMISSION ⋈ REPORTINGOWNER ⋈ NONDERIV_TRANS on `ACCESSION_NUMBER`.
- **Reuse surface confirmed:** `application/precision_metrics.py` exposes
  `moving_block_bootstrap(values, n_resamples, block_size, seed)` returning `ci_low`,
  `ci_high`, `p_value_ge_0` — the per-series CI both legs need. (`application/ic_analysis.py`
  `spearman_ic`/`aggregate_ic` are NOT used by the gate — see §4 event-study amendment;
  they may be reported descriptively only.)

## 4. Pre-registered gate — event-study abnormal return (LOCKED, amended 2026-06-09)

**Amendment rationale:** the signal is a *binary* cluster event (§2). A Spearman rank-IC
needs a continuous cross-section and does not transfer to a binary flag. The natural
information measure for a binary event is the **abnormal return** (standard event study).
This amends the original IC framing while still **blind to results** (pre-registration
intact). Approved 2026-06-09.

Run within each liquidity tercile. **Primary test = bottom (least-liquid) tercile**;
mid/top are descriptive only (show liquidity-dependence, cannot move the verdict).
Horizon: **21 trading days**, single gate.

**Abnormal return per cluster event** (market-adjusted, beta = 1):
`abn = name_21d_return − benchmark_21d_return`, over the same calendar window starting the
first trading day on/after the cluster fire (filing) date. **Benchmark = liquidity-tercile-
matched ETF** (pre-registered): bottom → `IWC` (iShares Micro-Cap), mid & top → `IWM`
(iShares Russell 2000). Events ordered by fire date; the series is moving-block
bootstrapped (block bootstrap absorbs overlapping-window / clustered-in-time correlation).

- **Leg 1 — information (gross):** series of gross `abn` per bottom-tercile event.
  **PASS iff** `moving_block_bootstrap(gross_abn).ci_low > 0`.
- **Leg 2 — tradeable (net):** `net_abn = gross_abn − slippage_bps/10000`, slippage by
  tercile (bottom **150** / mid **75** / top **40** bps round-trip per name).
  **PASS iff** `moving_block_bootstrap(net_abn).ci_low > 0`.

Bootstrap: `n_resamples = 1000`, `seed = 42` (project rule), 95% CI.

**Verdict (bottom tercile).** Because `net = gross − slippage` (slippage > 0), `net` can
never exceed `gross`; the four-cell table collapses to a clean 3-state:

| Condition | Verdict |
|-----------|---------|
| `net.ci_low > 0` (⇒ gross also > 0) | **PASS** → RESEARCH_ONLY edge; requires independent re-validation before any use |
| `gross.ci_low > 0` AND `net.ci_low ≤ 0` | **INCONCLUSIVE** — real information, killed by micro-cap costs (the ADR-052-expected outcome) |
| `gross.ci_low ≤ 0` | **KILL** → prediction permanently off the table (ADR-052) |

No magnitude floor (the old IC ≥ 0.02) is carried over — a 95% bootstrap CI lower bound
> 0 is the significance bar for each leg. Mean abnormal return + full distribution are
reported regardless of verdict.

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

**Caveat 3 — 10b5-1 flag exists but is historically under-populated.** Verified: SUBMISSION
carries an explicit `AFF10B5ONE` affirmation flag — cleaner than first assumed. We exclude
filings flagged `AFF10B5ONE`. BUT the field was sparsely populated before the SEC's 2023
mandatory-checkbox rule, so older clusters may include unflagged 10b5-1 plans. This adds
*noise* to the "non-routine" purity in a conservative direction (makes a PASS harder, not
easier), so it cannot manufacture a false positive. The flag is primarily a buy signal
concern anyway — 10b5-1 plans are overwhelmingly *sales*, and this signal is buys-only, so
contamination is structurally small. Documented; the unflagged-share by year is reported.

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
