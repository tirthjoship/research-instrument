# Unit C — Anti-Overtrade Throttle, Cash-Buffer Policy, Adherence Logging

**Date:** 2026-06-10 · **Status:** Approved (brainstorm complete)
**Parent:** Strategic wrap plan (`2026-06-10-strategic-wrap-plan-design.md`), build-week item 2–3.
**Branch:** `feat/unit-c-adherence` (off develop)

## Purpose

Close the behavior channel of the wrap plan: deterministic, advisory-only (L0)
checks that (a) flag overtrading, (b) flag cash-buffer breaches, and (c) measure
the user's own behavior gap — "tool said X, user did Y, gap P&L" — feeding the
Dec 2026 self-experiment review (literature anchor ~848 bps/yr disposition effect).

Everything deterministic, fail-loud, zero-touch weekly (per wrap plan §5).
No new external dependencies. No LLM in the verdict path.

## Decisions (locked during brainstorm)

| Question | Decision |
|---|---|
| Trade data source | **Holdings-diff weekly** — diff consecutive weekly snapshots; no manual entry. Known limit: intra-week round-trips invisible. |
| Overtrade metric | **Trade count/week** — flag when detected trades / weeks elapsed > `max_trades_per_week` (default 3). |
| Cash-buffer rule | **Min % floor** — cash ≥ `floor_pct` (default 5%) of portfolio value. |
| Cash source | **Config file** — gitignored `data/personal/cash.json` `{"cash_cad": ..., "as_of": "YYYY-MM-DD"}`; >28d stale ⇒ `STALE_CASH` flag, never silent pass. |
| Gap P&L | **21d counterfactual** — same horizon and PriceProvider machinery as the existing `resolve_flags()` Brier resolver. |
| Architecture | **Approach A: extend existing discipline pipeline** — quantity added to existing log rows; new pure `domain/adherence.py`; step 4 in Saturday script. (Rejected B: separate snapshot subsystem — more surface for a project closing ~Jun 29.) |

## Domain layer — `domain/adherence.py` (pure stdlib)

**DetectedTrade** (frozen dataclass): `ticker, action (BUY|SELL|NEW|EXIT),
qty_before, qty_after, week_of`.

- `diff_holdings(prev: dict[str, float], curr: dict[str, float], min_change_pct=0.005) -> list[DetectedTrade]`
  Quantity deltas between consecutive weekly snapshots. `min_change_pct` filters
  DRIP/rounding noise. Splits are NOT adjusted in v1 (a 2× qty jump counts as a
  trade) — documented limitation.
- `throttle_check(trades, weeks_elapsed, max_trades_per_week=3) -> ThrottleResult`
  Verdict `OK | OVERTRADE`. Evaluated per consecutive-snapshot pair;
  `weeks_elapsed = max(1.0, days_between_snapshots / 7)`, so a missed Saturday
  never produces a false flag.
- `cash_buffer_check(cash, portfolio_value, floor_pct=0.05, cash_as_of, now, max_stale_days=28) -> BufferResult`
  Verdict `OK | BUFFER_BREACH | STALE_CASH`.
- `match_flag(flag, subsequent_trades) -> FOLLOWED | PARTIAL | IGNORED`
  Only REDUCE/TRIM flags create obligations (ADD_OK/HOLD/REVIEW expect no
  action). Window = 21 days (matches Brier horizon). Position cut ≥50% ⇒
  FOLLOWED; some cut ⇒ PARTIAL; none ⇒ IGNORED.

**Gap P&L sign convention:** positive gap = following the tool would have saved
money.

- `flag_value = price × quantity` from the log row at flag time.
- IGNORED REDUCE/TRIM: `gap = flag_value × (−r_21d)`
- PARTIAL: gap on the retained fraction only
- FOLLOWED: gap = 0 by construction
- Reporting mirrors the Brier resolver's REDUCE/TRIM split: REDUCE-only gap is
  the headline self-experiment number (bps of portfolio value); TRIM gap is
  reported separately for transparency (TRIM is sizing advice, not a down-call,
  and historically TRIM names keep rising — a negative TRIM gap is honest data).

## Application layer

**Snapshot extension:** `holdings-risk` logged rows gain `quantity` and
`market_value` keys. Backward compatible: old rows lack the keys; diffing starts
once ≥2 snapshots carry quantity; first run logs `NO_BASELINE` and detects no
trades.

**Use case `application/adherence.py`:**
1. Read `discipline_log.jsonl`, group rows by `as_of` → weekly snapshots.
2. Diff consecutive snapshots → detected trades.
3. Throttle + cash-buffer checks.
4. Match open REDUCE/TRIM flags (≤21d old) against trades → adherence verdicts.
5. Resolve gap P&L for flags whose 21d horizon elapsed (PriceProvider callable,
   same pattern as `resolve_flags`).
6. Append adherence records to separate gitignored
   `data/personal/adherence_log.jsonl` (assessment-log schema untouched).
7. Print summary: trades detected, throttle verdict, buffer verdict, per-flag
   adherence, cumulative gap bps.

**CLI:** new `adherence-report` subcommand
(`--log`, `--cash-config`, `--adherence-log` paths).

**Cron:** `scripts/discipline_weekly_review.sh` gains step 4, output appended to
`data/reports/discipline_weekly_review.log`. Fail-loud like existing steps.

## Edge cases

- Missing snapshot week → `weeks_elapsed` denominator absorbs it.
- Delisted ticker → log + skip (consistent with hardening auto-prune).
- No cash.json → `STALE_CASH`-style loud skip, never silent OK.
- First run / single snapshot → `NO_BASELINE`, no trades, no flags.

## Testing

TDD. Small fixtures, fake PriceProvider, no real APIs. Hypothesis property
tests for `diff_holdings`: `diff(x, x) == []`; every emitted trade corresponds
to an actual qty change above threshold; noise-filter monotonicity. Unit tests
per verdict branch (throttle, buffer, match). One end-to-end CLI test with tmp
dirs (pattern: C1 regression test). mypy strict on new modules (runs clean once
venv hardening lands).

## Out of scope

- Broker-export parsing, manual trade entry (rejected sources).
- Split adjustment in holdings-diff.
- Mark-to-market counterfactual portfolio tracking (rejected: too much state).
- Any blocking/gating of trades — tool stays advisory at L0 until mid-July gate.
