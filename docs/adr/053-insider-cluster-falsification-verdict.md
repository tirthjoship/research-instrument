# ADR-053: Sub-$1B Insider-Cluster Falsification — Verdict (Unit B)

**Date:** 2026-06-10
**Status:** Accepted (2026-06-10) — full 2006–2024 verdict: **INCONCLUSIVE_THIN_COVERAGE → practical KILL** (pre-committed tree applied; prediction permanently closed).
**Deciders:** Tirth Joshi
**Builds on:** ADR-052 (CRO direction; Unit B = the one sanctioned predictive swing), ADR-039/043/044/046/049/050 (six prior falsifications), ADR-048/051 (forward gate + anti-p-hacking discipline)

## Context

ADR-052 closed the alpha hunt and sanctioned exactly one remaining predictive test: **sub-$1B non-routine insider-buy clusters** — the only idea with a *structural* non-arbitrage argument (institutions cannot fit into ~$300M names, so a retail-size investor has a real execution advantage). It was pre-registered as low-odds and killable: **KILL ⇒ prediction permanently off the table.** "The danger is a false positive, not build difficulty" — so the gate, not the build, is the integrity core.

Thresholds were LOCKED via pre-registration before any run, with build and verification kept as separate phases (heavier rigor on verification).

## Methodology (LOCKED — pre-registered, unchanged after seeing data)

- **Signal — strict cluster:** ≥3 distinct insiders (`RPTOWNERCIK`), each an open-market purchase (`TRANS_CODE='P'` AND `TRANS_ACQUIRED_DISP_CD='A'`, shares>0), within a rolling 30-day window. Excludes codes S/M/A(grant)/G/F/C/W, equity-swap, and `AFF10B5ONE` (10b5-1) filings. **Fires on the FILING date** (point-in-time; the cluster is only knowable once the 3rd Form-4 is public) — never the transaction date.
- **Data:** SEC DERA "Insider Transactions" (Form 345) quarterly flat files, 2006q1→latest (verified live; new `sec_form345_dataset_adapter.py`). Forward prices + ADV via yfinance, delisting-aware.
- **Gate — event-study abnormal return** (amended from rank-IC because the signal is binary; standard event study fits a binary event). For each bottom-tercile cluster event: `abn = name_21d_return − benchmark_21d_return`, benchmark = liquidity-matched ETF (bottom → **IWC**). Two legs, each a moving-block bootstrap (n=1000, seed=42, 95% CI):
  - **Leg 1 (information, gross):** `CI_low(gross_abn) > 0`.
  - **Leg 2 (tradeable, net):** `net_abn = gross_abn − 150bps`; `CI_low(net_abn) > 0`.
- **Slippage (LOCKED):** round-trip per name by ADV tercile — bottom 150 / mid 75 / top 40 bps. **Liquidity (ADV) terciles replace market-cap terciles** (point-in-time, no shares-outstanding-history leakage; arguably truer to the capacity thesis — Caveat 1).
- **Verdict (3-state, since `net ≤ gross`):** `net.CI_low>0` → **PASS** (RESEARCH_ONLY, needs independent re-validation); `gross.CI_low>0 & net.CI_low≤0` → **INCONCLUSIVE** (real info, killed by costs); `gross.CI_low≤0` → **KILL**.
- **Guards (override):** bottom-tercile events < 100 → `INCONCLUSIVE_THIN_N`; bottom-tercile benchmarked-coverage < 80% → `INCONCLUSIVE_THIN_COVERAGE`.
- **Primary test = bottom (least-liquid) tercile.** Mid/top descriptive only.

## Amendment 2026-06-10 — validity repairs applied BEFORE the full-window run

Two detection-validity bugs found in code review were fixed after the smoke run
(2021–24) but before the full 2006–2024 verdict run. Recorded per the
pre-registration honesty rules (this is validity repair, not threshold tuning;
all gate thresholds remain locked):

- **M1 — joint-filing dedup.** One Form 4 filed jointly by N reporting owners was
  counted as N distinct insiders, so a single buy decision could fabricate a
  "cluster." Detection now requires ≥3 greedily-matched distinct
  (insider, accession) pairs. Expected effect: fewer fabricated events, so THIN_N
  risk rises — but the count drop is NOT guaranteed (verified by review fuzzing):
  deduplication can shift a cluster's fire date, which moves the 30-day re-fire
  suppression window and can unmask a second, fully legitimate cluster the old
  rule had masked. Either direction is honest.
- **M2 — point-in-time terciles.** Tercile assignment pooled ADV across the full
  sample and collided per ticker (all of a ticker's events took one ADV — the
  last record's). Binning is now per-event against the expanding distribution of
  events up to each fire date (`MIN_TERCILE_POPULATION = 30`, disclosure-only:
  early events are binned and counted, never deferred or dropped).
- **Hardening:** a non-finite ADV (bad price bar) now routes the event to the
  conservative no-price path (bottom denominator) instead of silently
  corrupting rank binning.

The smoke-run numbers below predate these fixes and are NOT comparable to the
full-window result.

## Results

### Smoke window — 2021Q1–2024Q4 (pipeline validation, 2026-06-10, PRE-amendment)

| Metric | Value |
|--------|-------|
| Cluster events (all terciles) | 5298 |
| Resolved (usable prices) | 3956 → **overall resolution 74.7%** |
| Unresolved (mostly delisted micro-caps) | 1342 |
| **Bottom-tercile events (primary n)** | **1632** (≫ 100 power guard) |
| Bottom-tercile benchmarked coverage | 100% |
| **Leg 1 — gross abnormal (mean / CI_low)** | **+1.62% / +0.41%** → PASS (real information) |
| **Leg 2 — net of 150bps (mean / CI_low)** | **+0.12% / −1.09%** → FAIL (not tradeable) |
| **Verdict** | **INCONCLUSIVE** |

**Reading:** sub-$1B insider clusters carry **real gross 21-day information** (~+1.6% abnormal vs IWC, CI clears zero) that **does not survive micro-cap slippage**. This is precisely the ADR-052 prediction. Survivorship works *in favor* of the edge (dropping delisted losers inflates the gross figure), yet Leg-2 still fails — so the "untradeable" conclusion is **robust under favorable bias.**

### Full window — 2006Q1–2024Q4 (definitive, pre-registered, M1/M2-amended run, 2026-06-10)

| Metric | Value |
|--------|-------|
| Cluster events (all terciles) | 28,866 |
| Records with trailing ADV / no-price | 15,403 / 13,463 → **overall resolution 53.0%** |
| Bottom-tercile population (primary denominator, incl. no-price) | **17,881** |
| Bottom-tercile benchmarked | 4,349 |
| **Bottom-tercile coverage** | **24.32%** (guard requires ≥ 80%) |
| Leg 1 / Leg 2 | **not evaluated** — coverage guard fired before the legs |
| Events binned below min tercile population | 29 (disclosure-only) |
| **Verdict** | **INCONCLUSIVE_THIN_COVERAGE → practical KILL** |

## Decision / Verdict

**INCONCLUSIVE_THIN_COVERAGE → practical KILL (final).** Executed per the
pre-committed decision tree (strategic wrap spec 2026-06-10 §2, locked BEFORE this
result existed): the M1/M2 amendment consumed the one allowed remediation re-run;
a still-thin result is final — **cannot validate ⇒ cannot ever trade.** Prediction
is permanently off the table (ADR-052 stands). Unit D stays parked (wrap spec §6).

**Why coverage collapsed (honest reading):** 46.6% of all cluster events
(13,463/28,866) have NO price bar at/after the fire date in free yfinance data —
delisted micro-caps and unmapped symbols across 19 years. The survivorship-honest
denominator (code-review C1) bins every one of them into the bottom tercile, exactly
as designed: residual survivorship drives coverage DOWN instead of fabricating a
clean-looking sample. The thin verdict is the C1 fix WORKING. The smoke run's 100%
coverage (and its tantalizing gross signal) was an artifact of a 4-year recent
window where most names still trade. A definitive test of this hypothesis requires
survivorship-bias-free paid data (CRSP/Sharadar) — out of scope for this project's
no-paid-data rail, hence final here.

Interpretation rule (pre-committed) as applied:
- ~~PASS~~ / ~~INCONCLUSIVE (cost-killed)~~ / ~~KILL (gross ≤ 0)~~ — not reached;
  the guard fired first.
- **THIN after the one remediation → practical KILL.** The rig (DERA adapter +
  cluster detection + event-study gate) remains reusable ONLY under a new
  pre-registration ADR with a survivorship-complete data source.

## Consequences

- The product is unchanged regardless of verdict: an honest deterministic CRO (risk + behavior + abstaining RESEARCH_ONLY screen + discipline). A non-PASS = closure, not loss (value was banked in Units A/C; this resolves the edge question).
- The falsification rig (DERA adapter + cluster detection + event-study gate) is reusable and pre-registered; any re-test must keep the locked thresholds or write a new pre-registration ADR.
- Honesty rails hold: thresholds locked pre-data; survivorship surfaced as a reported number, not hidden; abnormal-return method is standard and defensible.

## Caveats

1. **Liquidity (ADV) terciles, not market cap** — point-in-time, avoids shares-outstanding-history look-ahead; conscious deviation from ADR-052's "market-cap tercile" wording.
2. **Residual survivorship** — handled honestly after code-review C1. The bottom-tercile
   coverage guard denominator now includes **all** qualifying bottom-tercile events: ADV-only
   (delisted mid-window) records and no-price events (delisted-before-fire / unmapped symbols,
   conservatively binned to the least-liquid tercile). Residual survivorship therefore **drives
   coverage DOWN** toward `INCONCLUSIVE_THIN_COVERAGE` rather than vanishing into a spurious
   100%. `overall_resolution_rate` is also reported (smoke: 74.7%). Direction note: dropping
   delisted losers would *inflate* the gross edge, so any non-tradeable / thin-coverage result
   is the conservative read. (Pre-fix, the smoke read a misleading 100% coverage; the fix made
   the guard match spec §5.)
3. **10b5-1 flag (`AFF10B5ONE`) under-populated pre-2023** — some older clusters may include unflagged 10b5-1 plans; this adds noise (harder to PASS), cannot manufacture a false positive; buys-only signal makes contamination structurally small.
4. **Smoke ≠ definitive** — the 2021–2024 smoke is a 4-year sub-sample for pipeline validation; the pre-registered verdict is the full 2006–2024 window.
