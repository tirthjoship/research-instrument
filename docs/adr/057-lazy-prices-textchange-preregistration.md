# ADR-057: SEC Filing Text-Change Signal ("Lazy Prices") — Pre-Registration

**Date:** 2026-06-27
**Status:** PRE-REGISTERED (hypothesis + gates LOCKED before any data was collected)
**Deciders:** Tirth Joshi
**Supersedes/relates:** Eighth pre-registered test. Follows the falsification discipline of
ADR-039/043/044/046/049/050/053. Designed explicitly to dodge their recurring kill-modes.

---

## §1 Context — why this signal, after seven kills

Seven pre-registered tests failed or came back inconclusive. Their failure signatures,
ranked by lethality:

1. **CI-spans-zero (6/7).** Even positive point estimates died because a bootstrap CI on
   the central statistic included 0 (ADR-044 IC=0.0040; ADR-049 IC=0.0107; ADR-039 OOS).
2. **Transaction cost (2/7).** Real *gross* signal eroded to nothing net (ADR-046 lost
   3.2pp CAGR to churn; ADR-053 insider clusters +1.62% gross → −1.09% after 150bps).
3. **Coverage / structural data absence (3/7).** The signal's data simply did not exist
   for the universe (ADR-043 conviction dims var=0 on mid-caps; ADR-053 46.6% delisted).
4. **Regime-lock / survivorship (3/7).** In-sample edge that vanished out-of-sample.

Every prior signal was tested **in isolation** and was either a price/sentiment derivative
or required data absent for the universe. The text-change signal is materially different:

- **An independent information channel** — linguistic change in periodic filings, not price,
  sentiment, attention, or analyst data. Low prior correlation with every dead signal, which
  is exactly the property the Fundamental Law of Active Management rewards when combining.
- **Published, large, slow-moving edge.** Cohen, Malloy & Nguyen, *Journal of Finance* 75(3),
  2020: a portfolio long "non-changers" / short "changers" earned up to **188 bps/month** in
  abnormal returns (1995–2014). Crucially **no announcement effect** — returns accrue over
  *months* as the information later surfaces, implying genuine inattention and **low turnover**.
- **Free + point-in-time.** Filings are public with exact timestamps (SEC submissions API).

This is a credible test *against* semi-strong efficiency, not a remix of a dead idea.

---

## §2 Pre-Registration (LOCKED — exact thresholds quoted)

**Hypothesis (H1, one-sided):** Higher inter-filing text similarity (a "non-changer") predicts
a higher forward EXCESS return cross-sectionally. Equivalently, mean cross-sectional rank-IC
between `textchange_similarity` and forward excess return is **positive**.

**Universe:** S&P 500 ∪ NASDAQ-100 (~570 liquid large-caps), point-in-time constituents,
ticker→CIK alive on the cohort date. Delisted names binned conservatively (counted in the
coverage denominator, never silently dropped — ADR-053 C1 discipline). **Survivor-biased on
purpose**: this *favours* finding an edge, so a null result is the stronger conclusion.

**Window:** 2015-Q1 → 2024-Q4 (≥8 years, OUT-OF-SAMPLE vs the paper's 1995–2014). Spans the
2018 and 2022 drawdowns and 2020 crash — not a single-regime sample.

**Cohorts:** QUARTERLY filing cohorts (10-Q + 10-K). Quarterly — not annual — is a deliberate
choice to maximise cohort count (~40 vs ~10) and thus tighten the IC confidence interval; the
#1 kill-mode is a CI that spans zero, and few cohorts guarantee a wide CI.

**Horizon — PRIMARY 63 trading days (one quarter).** This DEVIATES from the project's default
21-day horizon, justified: Lazy Prices documents *no* announcement effect and returns that
accrue over months. Testing it at 21 days would mis-specify the signal. 126d and 252d are
SECONDARY/exploratory and do not move the gate. Forward return is name return − SPY over the
horizon (sector-ETF benchmark is an exploratory robustness check only).

**Signal construction:** `textchange_similarity` = mean cosine similarity across the
informative sections (management discussion, litigation, risk factors — the paper's most
predictive) between a filing and its prior comparable (same form, one fiscal year earlier).
HIGH = non-changer. Computed only from text filed **≥1 business day** before the cohort date
(no intraday leak). Missing section pair → event dropped, never imputed (no forward-fill).

**Primary gate (cross-sectional rank-IC):**
- Per-cohort Spearman rank-IC of similarity vs forward excess return.
- Moving-block bootstrap CI on the per-cohort IC series (`domain/bootstrap.py`,
  block_size ∝ √n, n_resamples=2000, deterministic seed).
- **PRIMARY PASS iff `ic_ci_low > 0` AND `mean_ic ≥ 0.02`.**

**Secondary gate (tradeable, net-of-cost — orthogonal to primary):**
- Quarterly long top-tercile-similarity / short bottom-tercile basket.
- **Net of 50 bps per side** (both legs; liquid large-cap, quarterly turnover).
- Moving-block bootstrap CI on the per-cohort net long-short return series.
- **SECONDARY PASS iff `ls_net_ci_low > 0`.**

**Guards (fire BEFORE primary/secondary — pre-committed order):**
- `coverage < 0.80` → **INCONCLUSIVE_THIN_COVERAGE** (verdict deferred).
- `n_cohorts < 20` OR `n_events < 1000` → **INCONCLUSIVE_THIN_N**.

**Locked decision tree** (implemented in `application/lazy_prices_backtest.py::classify_lazy_prices`):
```
if coverage < 0.80:                 INCONCLUSIVE_THIN_COVERAGE
elif n_cohorts < 20 or n_events < 1000: INCONCLUSIVE_THIN_N
elif ic_ci_high < 0:                HALT_NEGATIVE          # significantly wrong-signed
elif primary_pass and secondary_pass: PASS
elif primary_pass:                  CONDITIONAL_PASS_PRIMARY_ONLY  # IC real, net basket didn't confirm
else:                               INCONCLUSIVE
```
Note: full **PASS requires BOTH** the IC gate and the net-of-cost basket (AND, not OR). This is
stricter than ADR-049's OR gate and is deliberate — given that costs killed two priors, a
cross-sectional IC that does not survive as a tradeable net basket is not a green light.

**Honest ceiling stated up front:** even if it clears, the realistic expectation after
post-publication decay (~58%, McLean–Pontiff) is single-digit annual gross. A PASS earns the
right to **forward-track**, nothing more. It is not a claim of alpha.

**Tuning forbidden:** thresholds above are final. One re-run is permitted only to fix a
validity bug found before the verdict (ADR-053 M1/M2 precedent), thresholds unchanged. Any
threshold change requires a NEW ADR with fresh data.

---

## §3 Results

NOT YET RUN. The rig is scaffolded and unit-tested; the live verdict run is gated on the
EDGAR document-text extraction hardening (see `sec_filing_text_adapter.py` EXTRACTION TODO)
and a one-time historical filing-text fetch. Report will be written to
`data/reports/lazy_prices_ic_63d_<date>.json` with the verdict, CI bounds, n, and coverage.

## §4 Verdict Reading

Pending §3.

## §5 Consequences

- **On PASS:** fold `textchange_similarity` into the multi-signal combination layer (research
  note `research/2026-06-27-alpha-signal-hunt.md`, candidate #4) and begin forward-tracking
  via the existing CallOutcome scorecard. Still labelled RESEARCH_ONLY until forward IC accrues.
- **On any INCONCLUSIVE/HALT:** record the honest null in a verdict ADR (058), keep the rig
  (`filing_textchange_service`, `sec_filing_text_adapter`, `LazyPricesBacktestUseCase`) as a
  reusable baseline, and do not relitigate without survivorship-complete paid filing data.
- **Either way:** the text-change adapter is reusable for descriptive features on the Stock
  Analysis tab (e.g. "this 10-K changed materially vs last year") independent of the verdict.
