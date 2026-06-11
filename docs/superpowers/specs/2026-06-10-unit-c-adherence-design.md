# Unit C — Anti-Overtrade Throttle, Cash-Buffer Policy, Adherence Logging

**Date:** 2026-06-10 · **Status:** Approved + validated (2 Opus reviews, 13 fixes applied)
**Parent:** Strategic wrap plan (`2026-06-10-strategic-wrap-plan-design.md`), build-week item 2–3.
**Branch:** `feat/unit-c-adherence` (off develop)

## Purpose

Close the behavior channel of the wrap plan: deterministic, advisory-only (L0)
checks that (a) flag overtrading, (b) flag cash-buffer breaches, and (c) measure
the user's own behavior gap — "tool said X, user did Y, gap P&L" — feeding the
Dec 2026 self-experiment review (literature anchor ~848 bps/yr disposition effect,
context only — see Interpretation limits).

Everything deterministic, fail-loud, zero-touch weekly (per wrap plan §5).
No new external dependencies. No LLM in the verdict path. No FX feed.

## Decisions (locked during brainstorm + validation)

| Question | Decision |
|---|---|
| Trade data source | **Holdings-diff weekly** — diff consecutive weekly snapshots; no manual entry. Known limit: intra-week round-trips invisible. |
| Overtrade metric | **Discretionary trade count/week** — tool-directed trades exempt (see Throttle). Default threshold 3. |
| Cash-buffer rule | **Min % floor** — cash ≥ `floor_pct` (default 5%) of CAD portfolio value. |
| Cash source | **Config file** — gitignored `data/personal/cash.json` `{"cash_cad": ..., "as_of": "YYYY-MM-DD"}`; >28d stale ⇒ `STALE_CASH` flag, never silent pass. |
| Gap P&L | **21d counterfactual at canonical fraction f=0.5** — same horizon and PriceProvider machinery as the existing `resolve_flags()` Brier resolver. |
| Currency | **CAD throughout** — `market_value_cad = book_value_cad × (1 + unrealized_pct)`; reuses already-CAD book values, no FX dependency. Native-currency market values from the CSV are NOT used. |
| Architecture | **Approach A: extend existing discipline pipeline** — quantity + market_value_cad added to existing log rows; new pure `domain/adherence.py`; step 4 in Saturday script. (Rejected B: separate snapshot subsystem — more surface for a project closing ~Jun 29.) |

## Domain layer — `domain/adherence.py` (pure stdlib)

**DetectedTrade** (frozen dataclass): `ticker, action (BUY|SELL|NEW|EXIT),
qty_before, qty_after, week_of`.

- `diff_holdings(prev: dict[str, float], curr: dict[str, float], sell_min_change_pct=0.005, buy_min_change_pct=0.02) -> list[DetectedTrade]`
  Quantity deltas between consecutive weekly snapshots. Asymmetric noise filter:
  SELL threshold 0.5%; BUY threshold 2% — the DRIP band (dividend reinvestment
  adds small BUY-side quantity that is not a discretionary trade and must not
  pollute the throttle).
  **Split guard:** any single-week quantity ratio within ±2% of a common split
  factor (2.0, 3.0, 1.5, 0.5, 1/3) is emitted as `SUSPECTED_SPLIT`, excluded
  from trades AND from gap math for that ticker, and logged loudly (fail-loud).
  Rationale: provider prices are split-adjusted; logged quantities are not —
  an unguarded split fabricates a 100% BUY and corrupts `flag_value` continuity.
- `throttle_check(discretionary_trades, weeks_elapsed, max_trades_per_week=3) -> ThrottleResult`
  Verdict `OK | OVERTRADE`. **Input is discretionary trades only:**
  `discretionary = detected_trades − trades matched to open REDUCE/TRIM flags`.
  Obeying the tool can never trip the throttle (otherwise following 4 REDUCE
  flags in one week flags OVERTRADE — perverse incentive).
  `weeks_elapsed = max(1.0, days_between_snapshots / 7)`, so a missed Saturday
  never produces a false flag. Disclosure semantics: holdings-diff counts are a
  **lower bound** ("net weekly position changes"; intra-week round trips
  invisible) — report wording must say so.
- `cash_buffer_check(cash_cad, portfolio_value_cad, floor_pct=0.05, cash_as_of, now, max_stale_days=28) -> BufferResult`
  Verdict `OK | BUFFER_BREACH | STALE_CASH`. Missing cash.json ⇒ `STALE_CASH`
  loud skip, never silent OK.
- `match_flag(flag, subsequent_trades) -> FOLLOWED | PARTIAL | IGNORED`
  Only REDUCE/TRIM flags create obligations (ADD_OK/HOLD/REVIEW expect no
  action). Window = 21 days (matches Brier horizon). Labels derive from the
  canonical fraction: `actual_cut ≥ f` ⇒ FOLLOWED; `0 < actual_cut < f` ⇒
  PARTIAL; `0` ⇒ IGNORED.

**One open obligation per ticker (anti-double-count):** `grade_position` is
deterministic, so a broken name re-flags REDUCE every Saturday. Each weekly
re-flag must NOT open a new obligation: while a ticker has an unresolved
obligation (<21d old, same verdict direction), new flags for it are suppressed.
Property test: N consecutive identical flags ⇒ exactly 1 obligation.
Without this, the same drop is counted up to 4× and cumulative gap bps inflates
mechanically with flag frequency, not behavior.

**Gap P&L — single canonical formula.** The counterfactual "tool action" is
cutting fraction `f = 0.5` of the position (the same `f` used for labels — the
label threshold and the P&L fraction are one number by design):

```
gap = flag_value × max(0, f − actual_cut_fraction) × (−r_21d)
```

- `flag_value = price × quantity` from the log row at flag time (CAD-consistent
  via market_value_cad; see Application).
- IGNORED (`actual_cut = 0`): `gap = flag_value × f × (−r_21d)`.
- PARTIAL: scales with the shortfall vs `f`.
- FOLLOWED (`actual_cut ≥ f`): gap = 0 — now true by construction, not by fiat.
- Sign convention: positive gap = following the tool would have saved money.
- **Proceeds assumption (explicit):** counterfactual sale proceeds sit in cash
  at 0% for the 21 days. This isolates the name-specific avoid-the-drop effect.
  Known sensitivity, not modeled in v1: reinvest-in-SPY alternative
  (`gap = flag_value × f' × (r_SPY_21d − r_21d)`).

**Bps normalization + annualization (defined, not vibes):**
- Per-flag: `gap_bps_i = gap_dollar_i / portfolio_value_cad_at_flag_as_of × 1e4`
  — each flag self-normalizing against the portfolio value at ITS flag date,
  so differently-sized epochs are additive.
- Headline = Σ gap_bps_i over REDUCE obligations, reported BOTH as observed
  cumulative over the actual window AND annualized (`× 365 / days_observed`),
  clearly labeled. Only the annualized figure sits next to the 848 bps/yr
  anchor, and only as context.
- Reporting mirrors the Brier resolver's REDUCE/TRIM split: REDUCE-only gap is
  the headline; TRIM gap reported separately for transparency (TRIM is sizing
  advice, not a down-call — a negative TRIM gap is honest data).

## Application layer

**Snapshot extension:** logged rows gain `quantity` and `market_value_cad`.
- `market_value_cad = book_value_cad × (1 + unrealized_pct)` — both inputs are
  already CAD (`Book Value (CAD)` column + computed unrealized_pct). The CSV's
  native `Market Value` column (mixed CAD/USD) is never summed.
- Plumbing note: `PositionRisk` currently has no shares/market_value
  (domain/models.py:407-424) and `execute()` discards `Holding.shares`
  (holdings_risk.py:99-103). Either extend `PositionRisk` (preferred — keeps
  CLI thin) or zip positions with holdings at the row-construction site
  (cli.py:2114-2126).
- Backward compatible: legacy rows lack the keys — all readers use
  `row.get("quantity")`, never `row["quantity"]` (hundreds of legacy rows
  exist). Diffing starts once ≥2 snapshots carry quantity; first run logs
  `NO_BASELINE`, no trades.

**Snapshot grouping:** group rows by `as_of` **date** (`.date()`), NOT the raw
microsecond timestamp — matches the existing convention in
`calibration_readiness.py` and makes same-week re-runs sane. Same-day re-run
rule: keep the latest run per date (rows from the max `as_of` timestamp on that
date).

**Use case `application/adherence.py`:**
1. Read `discipline_log.jsonl`, group rows by `as_of` date → weekly snapshots.
2. Diff consecutive snapshots → detected trades (+ SUSPECTED_SPLIT exclusions).
3. Match open REDUCE/TRIM obligations against trades → adherence verdicts;
   apply one-obligation-per-ticker rule.
4. Throttle on discretionary trades; cash-buffer check.
5. Resolve gap P&L for obligations whose 21d horizon elapsed (PriceProvider
   callable, same pattern as `resolve_flags`).
6. Append adherence records to separate gitignored
   `data/personal/adherence_log.jsonl`.
   **Idempotency:** records keyed by `(flag_ticker, flag_as_of_date)`; on
   re-run, existing keys are skipped, never duplicated (append-only file,
   re-runnable report).
7. Print summary: trades detected (+ split/DRIP exclusions), throttle verdict,
   buffer verdict, per-flag adherence, cumulative + annualized gap bps,
   **and `skipped_unresolved` count + tickers** with the caption: "N flags
   excluded for missing 21d prices (incl. delistings); gap is conservative."
   (Survivorship disclosed, not silent — delisted names are exactly the
   biggest would-have-saved cases.)

**CLI:** new `adherence-report` subcommand following the existing click
pattern (`@cli.command`, `--log` / `--cash-config` / `--adherence-log` options
with `data/personal/...` defaults, `show_default=True`, lazy imports,
`click.echo` output — template: `resolve-discipline-flags`, cli.py:2137).

**Cron:** `scripts/discipline_weekly_review.sh` gains step 4, output appended
to `data/reports/discipline_weekly_review.log`. Same `"$PYTHON" -m
application.cli` + `set -euo pipefail` fail-loud pattern as steps 1–3.

## Edge cases

- Missing snapshot week → `weeks_elapsed` denominator absorbs it.
- Delisted ticker → log + skip + counted in `skipped_unresolved` (consistent
  with hardening auto-prune).
- No cash.json / stale → loud `STALE_CASH`, never silent OK.
- First run / single snapshot → `NO_BASELINE`, no trades, no flags.
- Suspected split → excluded + loud log (see split guard).
- Same-day re-runs → latest-run-per-date rule; adherence idempotency key
  prevents duplicate records.

## Interpretation limits (pre-registered for Dec 2026 review)

The self-experiment is **descriptive, underpowered by design, directional at
best**. Expected distinct REDUCE obligations over 6 months: low tens (the ~23
REDUCE verdicts in a snapshot are mostly the same broken names re-flagging;
dedup collapses them), on correlated equities with overlapping 21d windows.
The Dec review reports: point estimate + n + skipped_unresolved count.
**No significance test, no CI, no "beats/misses the literature" verdict.**
The 848 bps/yr figure appears as scale context only.

## Testing

TDD. Small fixtures, fake PriceProvider, no real APIs. Hypothesis property
tests for `diff_holdings`: `diff(x, x) == []`; every emitted trade corresponds
to a qty change above its side's threshold; noise-filter monotonicity; split
ratios never emit trades. Property test for obligations: N consecutive
identical flags ⇒ 1 obligation. Unit tests per verdict branch (throttle incl.
tool-directed exemption, buffer incl. stale/missing, match incl. f-threshold
boundary). One end-to-end CLI test with tmp dirs (pattern:
`tests/application/test_cli_insider.py` C1 regression test). mypy strict on new
modules (runs clean once venv hardening lands).

## Out of scope

- Broker-export parsing, manual trade entry (rejected sources).
- Split ADJUSTMENT (guard + exclude only; no quantity restatement in v1).
- FX feed / native-currency market values.
- Mark-to-market counterfactual portfolio tracking (rejected: too much state).
- SPY-reinvestment counterfactual (documented sensitivity only).
- Any blocking/gating of trades — tool stays advisory at L0 until mid-July gate.

## Validation log

2026-06-10: two parallel Opus reviews. Codebase-accuracy review: 2 inaccuracies
(market_value plumbing, CAD normalization) + 5 gaps — all fixed above.
Methodology review: 3 BLOCKERs (counterfactual fraction mismatch, repeated-flag
double-count, undefined bps normalization) + 6 should-fix/notes — all fixed
above. Architecture verdict: sound; measurement defects were definitional and
resolved at spec level.
