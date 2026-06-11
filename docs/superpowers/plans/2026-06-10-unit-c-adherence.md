# Unit C — Adherence/Throttle/Cash-Buffer Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Deterministic advisory checks — holdings-diff trade detection, discretionary-trade throttle, CAD cash-buffer floor, and 21d-counterfactual adherence gap logging — per validated spec `docs/superpowers/specs/2026-06-10-unit-c-adherence-design.md` (v4).

**Architecture:** Pure domain module `domain/adherence.py` (stdlib only: dataclasses/datetime/enum/typing) computes everything from plain values. Application layer (`application/adherence.py`) feeds it from `discipline_log.jsonl` snapshots + PriceProvider, appends idempotently to `adherence_log.jsonl`. CLI subcommand + Saturday cron step 4. Log rows gain `quantity` + `market_value_cad` (FX via existing yfinance provider, `USDCAD=X`).

**Tech Stack:** Python 3.12, click CLI, pytest + Hypothesis, mypy strict. No new dependencies.

**Branch:** `feat/unit-c-adherence` (already created, spec committed).

**Constants (from spec, do not re-derive):** canonical fraction `f = 0.5`; horizon 21d; throttle default 3/week; cash floor 5%; stale cash 28d; SELL noise filter 0.5%; BUY/DRIP filter 2%; split factors {2.0, 3.0, 1.5, 0.5, 1/3} ±2%.

---

### Task 1: Domain types + `diff_holdings` (incl. split guard + asymmetric noise filter)

**Files:**
- Create: `domain/adherence.py`
- Test: `tests/domain/test_adherence_diff.py`

- [ ] **Step 1: Write the failing tests**

```python
"""tests/domain/test_adherence_diff.py"""
from datetime import date

from hypothesis import given
from hypothesis import strategies as st

from domain.adherence import DetectedTrade, TradeAction, diff_holdings

WEEK = date(2026, 6, 13)


def test_no_change_no_trades() -> None:
    h = {"AC.TO": 30.0, "ARKK": 12.0}
    assert diff_holdings(h, h, WEEK) == []


def test_new_position_detected() -> None:
    trades = diff_holdings({}, {"AC.TO": 30.0}, WEEK)
    assert trades == [
        DetectedTrade("AC.TO", TradeAction.NEW, 0.0, 30.0, WEEK)
    ]


def test_exit_position_detected() -> None:
    trades = diff_holdings({"AC.TO": 30.0}, {}, WEEK)
    assert trades == [
        DetectedTrade("AC.TO", TradeAction.EXIT, 30.0, 0.0, WEEK)
    ]


def test_sell_above_threshold_detected() -> None:
    trades = diff_holdings({"AC.TO": 100.0}, {"AC.TO": 50.0}, WEEK)
    assert trades[0].action is TradeAction.SELL


def test_sell_below_threshold_filtered() -> None:
    # 0.3% decrease < 0.5% sell filter
    assert diff_holdings({"AC.TO": 1000.0}, {"AC.TO": 997.0}, WEEK) == []


def test_drip_sized_buy_filtered() -> None:
    # 1% increase < 2% BUY/DRIP filter
    assert diff_holdings({"AC.TO": 100.0}, {"AC.TO": 101.0}, WEEK) == []


def test_buy_above_drip_band_detected() -> None:
    trades = diff_holdings({"AC.TO": 100.0}, {"AC.TO": 110.0}, WEEK)
    assert trades[0].action is TradeAction.BUY


def test_two_for_one_split_flagged_not_buy() -> None:
    trades = diff_holdings({"AC.TO": 100.0}, {"AC.TO": 200.0}, WEEK)
    assert trades[0].action is TradeAction.SUSPECTED_SPLIT


def test_reverse_split_flagged_not_sell() -> None:
    trades = diff_holdings({"AC.TO": 100.0}, {"AC.TO": 50.5}, WEEK)
    # 0.505 ratio is within ±2% of 0.5 -> split, not SELL
    assert trades[0].action is TradeAction.SUSPECTED_SPLIT


@given(
    st.dictionaries(
        st.text(min_size=1, max_size=6), st.floats(1.0, 1e6), max_size=20
    )
)
def test_property_self_diff_is_empty(holdings: dict[str, float]) -> None:
    assert diff_holdings(holdings, holdings, WEEK) == []


@given(
    prev=st.floats(1.0, 1e6),
    curr=st.floats(1.0, 1e6),
)
def test_property_every_trade_has_real_change(prev: float, curr: float) -> None:
    trades = diff_holdings({"X": prev}, {"X": curr}, WEEK)
    for t in trades:
        assert t.qty_before != t.qty_after
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/domain/test_adherence_diff.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'domain.adherence'`

- [ ] **Step 3: Write the implementation**

```python
"""domain/adherence.py — Unit C pure primitives (stdlib only).

Holdings-diff trade detection, discretionary-trade throttle, CAD cash-buffer
floor, one-obligation-per-ticker adherence matching, and the canonical
21d-counterfactual gap formula (f = 0.5). Spec:
docs/superpowers/specs/2026-06-10-unit-c-adherence-design.md. The deterministic
core computes verdicts; nothing here fetches data or touches files."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from enum import Enum

# Canonical counterfactual fraction: the "tool action" for a REDUCE/TRIM flag
# is cutting this fraction of the position. Label threshold and P&L fraction
# are this one number BY DESIGN (spec blocker #1) — never use two values.
CANONICAL_CUT_FRACTION = 0.5

_SELL_MIN_CHANGE_PCT = 0.005  # below this a decrease is rounding noise
_BUY_MIN_CHANGE_PCT = 0.02  # below this an increase is DRIP, not a trade
_SPLIT_FACTORS = (2.0, 3.0, 1.5, 0.5, 1.0 / 3.0)
_SPLIT_TOLERANCE = 0.02  # ±2% of a known split ratio


class TradeAction(str, Enum):
    BUY = "BUY"
    SELL = "SELL"
    NEW = "NEW"
    EXIT = "EXIT"
    SUSPECTED_SPLIT = "SUSPECTED_SPLIT"


@dataclass(frozen=True)
class DetectedTrade:
    ticker: str
    action: TradeAction
    qty_before: float
    qty_after: float
    week_of: date


def _is_split_ratio(ratio: float) -> bool:
    return any(abs(ratio - f) / f <= _SPLIT_TOLERANCE for f in _SPLIT_FACTORS)


def diff_holdings(
    prev: dict[str, float],
    curr: dict[str, float],
    week_of: date,
    sell_min_change_pct: float = _SELL_MIN_CHANGE_PCT,
    buy_min_change_pct: float = _BUY_MIN_CHANGE_PCT,
) -> list[DetectedTrade]:
    """Quantity deltas between two weekly snapshots. Asymmetric noise filter
    (SELL 0.5%, BUY 2% — the DRIP band). Quantity ratios near common split
    factors are SUSPECTED_SPLIT: provider prices are split-adjusted but logged
    quantities are not, so an unguarded split fabricates a 100% BUY."""
    trades: list[DetectedTrade] = []
    for ticker in sorted(set(prev) | set(curr)):
        p = prev.get(ticker, 0.0)
        c = curr.get(ticker, 0.0)
        if p <= 0 and c > 0:
            trades.append(DetectedTrade(ticker, TradeAction.NEW, 0.0, c, week_of))
            continue
        if p > 0 and c <= 0:
            trades.append(DetectedTrade(ticker, TradeAction.EXIT, p, 0.0, week_of))
            continue
        if p <= 0 or c <= 0 or p == c:
            continue
        if _is_split_ratio(c / p):
            trades.append(
                DetectedTrade(ticker, TradeAction.SUSPECTED_SPLIT, p, c, week_of)
            )
            continue
        change = (c - p) / p
        if change <= -sell_min_change_pct:
            trades.append(DetectedTrade(ticker, TradeAction.SELL, p, c, week_of))
        elif change >= buy_min_change_pct:
            trades.append(DetectedTrade(ticker, TradeAction.BUY, p, c, week_of))
    return trades
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/domain/test_adherence_diff.py -v`
Expected: ALL PASS. (If `test_reverse_split_flagged_not_sell` fails: 50.5/100 = 0.505, |0.505−0.5|/0.5 = 0.01 ≤ 0.02 — must be split.)

- [ ] **Step 5: Commit**

```bash
git add domain/adherence.py tests/domain/test_adherence_diff.py
git commit -m "feat: holdings-diff trade detection with split guard + DRIP band (Unit C)"
```

---

### Task 2: `throttle_check` + `cash_buffer_check`

**Files:**
- Modify: `domain/adherence.py` (append)
- Test: `tests/domain/test_adherence_checks.py`

- [ ] **Step 1: Write the failing tests**

```python
"""tests/domain/test_adherence_checks.py"""
from datetime import date

from domain.adherence import (
    BufferVerdict,
    ThrottleVerdict,
    cash_buffer_check,
    throttle_check,
)


def test_throttle_ok_under_threshold() -> None:
    r = throttle_check(n_discretionary_trades=2, weeks_elapsed=1.0)
    assert r.verdict is ThrottleVerdict.OK
    assert r.trades_per_week == 2.0


def test_throttle_overtrade_above_threshold() -> None:
    r = throttle_check(n_discretionary_trades=4, weeks_elapsed=1.0)
    assert r.verdict is ThrottleVerdict.OVERTRADE


def test_throttle_exactly_at_threshold_is_ok() -> None:
    assert throttle_check(3, 1.0).verdict is ThrottleVerdict.OK


def test_throttle_gap_week_absorbed() -> None:
    # 4 trades over 2 weeks = 2/week -> OK
    assert throttle_check(4, 2.0).verdict is ThrottleVerdict.OK


def test_buffer_ok() -> None:
    r = cash_buffer_check(
        cash_cad=1000.0, portfolio_value_cad=10000.0,
        cash_as_of=date(2026, 6, 1), now=date(2026, 6, 13),
    )
    assert r.verdict is BufferVerdict.OK
    assert r.cash_pct == 1000.0 / 11000.0


def test_buffer_breach() -> None:
    r = cash_buffer_check(
        cash_cad=100.0, portfolio_value_cad=10000.0,
        cash_as_of=date(2026, 6, 1), now=date(2026, 6, 13),
    )
    assert r.verdict is BufferVerdict.BUFFER_BREACH


def test_buffer_stale_cash_beats_breach() -> None:
    r = cash_buffer_check(
        cash_cad=100.0, portfolio_value_cad=10000.0,
        cash_as_of=date(2026, 1, 1), now=date(2026, 6, 13),
    )
    assert r.verdict is BufferVerdict.STALE_CASH


def test_buffer_missing_portfolio_value_is_stale() -> None:
    r = cash_buffer_check(
        cash_cad=1000.0, portfolio_value_cad=None,
        cash_as_of=date(2026, 6, 1), now=date(2026, 6, 13),
    )
    assert r.verdict is BufferVerdict.STALE_CASH
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/domain/test_adherence_checks.py -v`
Expected: FAIL — `ImportError: cannot import name 'BufferVerdict'`

- [ ] **Step 3: Append implementation to `domain/adherence.py`**

```python
class ThrottleVerdict(str, Enum):
    OK = "OK"
    OVERTRADE = "OVERTRADE"


class BufferVerdict(str, Enum):
    OK = "OK"
    BUFFER_BREACH = "BUFFER_BREACH"
    STALE_CASH = "STALE_CASH"


@dataclass(frozen=True)
class ThrottleResult:
    verdict: ThrottleVerdict
    trades_per_week: float


@dataclass(frozen=True)
class BufferResult:
    verdict: BufferVerdict
    cash_pct: float | None


def throttle_check(
    n_discretionary_trades: int,
    weeks_elapsed: float,
    max_trades_per_week: float = 3.0,
) -> ThrottleResult:
    """Advisory overtrade flag on DISCRETIONARY trades only (tool-directed
    trades are exempt upstream — obeying 4 REDUCE flags must never trip this).
    Holdings-diff counts are a LOWER bound (intra-week round trips invisible);
    report wording must say 'net weekly position changes'."""
    weeks = max(1.0, weeks_elapsed)
    rate = n_discretionary_trades / weeks
    verdict = (
        ThrottleVerdict.OVERTRADE if rate > max_trades_per_week else ThrottleVerdict.OK
    )
    return ThrottleResult(verdict, rate)


def cash_buffer_check(
    cash_cad: float,
    portfolio_value_cad: float | None,
    cash_as_of: date,
    now: date,
    floor_pct: float = 0.05,
    max_stale_days: int = 28,
) -> BufferResult:
    """Cash >= floor_pct of total (cash + holdings, CAD). Stale or missing
    inputs are STALE_CASH — loud skip, never a silent OK (wrap plan §5)."""
    if portfolio_value_cad is None or (now - cash_as_of).days > max_stale_days:
        return BufferResult(BufferVerdict.STALE_CASH, None)
    total = cash_cad + portfolio_value_cad
    if total <= 0:
        return BufferResult(BufferVerdict.STALE_CASH, None)
    pct = cash_cad / total
    verdict = BufferVerdict.OK if pct >= floor_pct else BufferVerdict.BUFFER_BREACH
    return BufferResult(verdict, pct)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/domain/test_adherence_checks.py -v`
Expected: ALL PASS

- [ ] **Step 5: Commit**

```bash
git add domain/adherence.py tests/domain/test_adherence_checks.py
git commit -m "feat: discretionary throttle + CAD cash-buffer checks (Unit C)"
```

---

### Task 3: Obligations (one-per-ticker) + adherence labels + gap formula

**Files:**
- Modify: `domain/adherence.py` (append)
- Test: `tests/domain/test_adherence_gap.py`

- [ ] **Step 1: Write the failing tests**

```python
"""tests/domain/test_adherence_gap.py"""
from datetime import date

from hypothesis import given
from hypothesis import strategies as st

from domain.adherence import (
    CANONICAL_CUT_FRACTION,
    AdherenceLabel,
    Obligation,
    actual_cut_fraction,
    adherence_label,
    annualize_bps,
    build_obligations,
    gap_cad,
)


def _flag(ticker: str, d: date, verdict: str = "REDUCE") -> dict[str, object]:
    return {
        "ticker": ticker,
        "verdict": verdict,
        "as_of_date": d,
        "quantity": 100.0,
        "market_value_cad": 5000.0,
    }


def test_single_flag_one_obligation() -> None:
    obs = build_obligations([_flag("AC.TO", date(2026, 6, 13))])
    assert len(obs) == 1
    assert obs[0] == Obligation("AC.TO", "REDUCE", date(2026, 6, 13), 100.0, 5000.0)


def test_consecutive_weekly_reflag_suppressed() -> None:
    flags = [
        _flag("AC.TO", date(2026, 6, 13)),
        _flag("AC.TO", date(2026, 6, 20)),
        _flag("AC.TO", date(2026, 6, 27)),
    ]
    assert len(build_obligations(flags)) == 1  # property: N identical flags -> 1


def test_reflag_after_horizon_opens_new_obligation() -> None:
    flags = [
        _flag("AC.TO", date(2026, 6, 13)),
        _flag("AC.TO", date(2026, 7, 11)),  # 28d later > 21d horizon
    ]
    assert len(build_obligations(flags)) == 2


def test_reduce_and_trim_are_separate_tracks() -> None:
    flags = [
        _flag("AC.TO", date(2026, 6, 13), "REDUCE"),
        _flag("AC.TO", date(2026, 6, 13), "TRIM"),
    ]
    assert len(build_obligations(flags)) == 2


@given(st.integers(min_value=1, max_value=10))
def test_property_n_identical_flags_one_obligation(n: int) -> None:
    flags = [_flag("AC.TO", date(2026, 6, 13)) for _ in range(n)]
    assert len(build_obligations(flags)) == 1


def test_cut_fraction_cumulative_min_over_window() -> None:
    # qty 100 at flag; later weekly snapshots 80 then 40 inside window
    cut = actual_cut_fraction(100.0, [80.0, 40.0])
    assert cut == 0.6


def test_cut_fraction_rebuy_does_not_uncut() -> None:
    # sold to 40 then re-bought to 90: max cut reached is what counts
    assert actual_cut_fraction(100.0, [40.0, 90.0]) == 0.6


def test_labels_derive_from_canonical_fraction() -> None:
    assert adherence_label(0.5) is AdherenceLabel.FOLLOWED
    assert adherence_label(0.6) is AdherenceLabel.FOLLOWED
    assert adherence_label(0.2) is AdherenceLabel.PARTIAL
    assert adherence_label(0.0) is AdherenceLabel.IGNORED


def test_gap_ignored_full_shortfall() -> None:
    # ignored REDUCE, price fell 10%: gap = 5000 * 0.5 * 0.10 = +250 CAD
    assert gap_cad(5000.0, 0.0, -0.10) == 250.0


def test_gap_followed_is_zero() -> None:
    assert gap_cad(5000.0, 0.5, -0.10) == 0.0


def test_gap_partial_scales_with_shortfall() -> None:
    # cut 0.25 of position, shortfall 0.25: gap = 5000 * 0.25 * 0.10 = +125
    assert gap_cad(5000.0, 0.25, -0.10) == 125.0


def test_gap_negative_when_price_rises() -> None:
    # ignored flag but price rose: following would have COST money
    assert gap_cad(5000.0, 0.0, 0.10) == -250.0


def test_annualize() -> None:
    assert annualize_bps(100.0, days_observed=182.5) == 200.0


def test_canonical_fraction_is_single_source() -> None:
    assert CANONICAL_CUT_FRACTION == 0.5
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/domain/test_adherence_gap.py -v`
Expected: FAIL — `ImportError: cannot import name 'Obligation'`

- [ ] **Step 3: Append implementation to `domain/adherence.py`**

```python
HORIZON_DAYS = 21


class AdherenceLabel(str, Enum):
    FOLLOWED = "FOLLOWED"
    PARTIAL = "PARTIAL"
    IGNORED = "IGNORED"


@dataclass(frozen=True)
class Obligation:
    """One open tool-directed expectation: a REDUCE/TRIM flag on a position.
    One open obligation per (ticker, verdict) at a time — grade_position
    re-flags a broken name every Saturday, and without suppression the same
    drop is gap-counted once per week (spec blocker #4)."""

    ticker: str
    verdict: str
    flag_date: date
    quantity: float
    market_value_cad: float


def build_obligations(
    flag_rows: list[dict[str, object]], horizon_days: int = HORIZON_DAYS
) -> list[Obligation]:
    """flag_rows: REDUCE/TRIM log rows that carry quantity + market_value_cad
    + as_of_date (a datetime.date), in any order. While a (ticker, verdict)
    obligation is < horizon_days old, newer flags for it are suppressed."""
    obligations: list[Obligation] = []
    last_open: dict[tuple[str, str], date] = {}
    for row in sorted(flag_rows, key=lambda r: r["as_of_date"]):  # type: ignore[arg-type, return-value]
        ticker = str(row["ticker"])
        verdict = str(row["verdict"])
        flag_date = row["as_of_date"]
        assert isinstance(flag_date, date)
        key = (ticker, verdict)
        opened = last_open.get(key)
        if opened is not None and (flag_date - opened).days < horizon_days:
            continue
        last_open[key] = flag_date
        obligations.append(
            Obligation(
                ticker=ticker,
                verdict=verdict,
                flag_date=flag_date,
                quantity=float(row["quantity"]),  # type: ignore[arg-type]
                market_value_cad=float(row["market_value_cad"]),  # type: ignore[arg-type]
            )
        )
    return obligations


def actual_cut_fraction(qty_at_flag: float, later_quantities: list[float]) -> float:
    """CUMULATIVE reduction across the weekly snapshots inside the 21d window:
    the deepest cut reached counts, a later re-buy does not undo adherence."""
    if qty_at_flag <= 0 or not later_quantities:
        return 0.0
    deepest = min(later_quantities)
    return max(0.0, (qty_at_flag - deepest) / qty_at_flag)


def adherence_label(
    cut: float, f: float = CANONICAL_CUT_FRACTION
) -> AdherenceLabel:
    if cut >= f:
        return AdherenceLabel.FOLLOWED
    if cut > 0.0:
        return AdherenceLabel.PARTIAL
    return AdherenceLabel.IGNORED


def gap_cad(
    flag_value_cad: float,
    cut: float,
    r_21d: float,
    f: float = CANONICAL_CUT_FRACTION,
) -> float:
    """gap = flag_value × max(0, f − actual_cut) × (−r_21d).
    Positive gap = following the tool would have saved money. Counterfactual
    sale proceeds sit in cash at 0% for the window (spec: explicit assumption;
    isolates the name-specific avoid-the-drop effect)."""
    return flag_value_cad * max(0.0, f - cut) * (-r_21d)


def gap_bps(gap_dollar_cad: float, portfolio_value_cad_at_flag: float) -> float:
    """Per-flag bps against the portfolio value at THAT flag's date — each flag
    self-normalizing, so differently-sized epochs are additive (spec blocker #7)."""
    if portfolio_value_cad_at_flag <= 0:
        return 0.0
    return gap_dollar_cad / portfolio_value_cad_at_flag * 1e4


def annualize_bps(cumulative_bps: float, days_observed: float) -> float:
    """Only the annualized figure sits next to the ~848 bps/yr literature
    anchor, and only as context — never a significance claim."""
    if days_observed <= 0:
        return 0.0
    return cumulative_bps * 365.0 / days_observed
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/domain/test_adherence_gap.py -v`
Expected: ALL PASS

- [ ] **Step 5: Run mypy + full domain tests, then commit**

Run: `mypy domain/adherence.py && pytest tests/domain/ -v`
Expected: mypy clean (if mypy still missing from venv, note it and run tests only — venv hardening is a separate sprint), tests PASS.

```bash
git add domain/adherence.py tests/domain/test_adherence_gap.py
git commit -m "feat: obligations with one-per-ticker dedup + canonical f=0.5 gap formula (Unit C)"
```

---

### Task 4: Extend `PositionRisk` + holdings_risk plumbing (quantity, market_value_cad, FX)

**Files:**
- Modify: `domain/models.py:407-431` (PositionRisk)
- Modify: `application/holdings_risk.py`
- Test: `tests/application/test_holdings_risk_cad.py`

- [ ] **Step 1: Write the failing test**

```python
"""tests/application/test_holdings_risk_cad.py"""
from datetime import datetime, timedelta, timezone

from application.holdings_reader import Holding
from application.holdings_risk import HoldingsRiskAssessmentUseCase


class _FakeNarrator:
    def narrate(self, context: dict[str, object]) -> str:
        return "test"


def _series(px: float) -> list[tuple[datetime, float]]:
    start = datetime(2024, 1, 1)
    return [(start + timedelta(days=i), px) for i in range(260)]


def _provider(ticker: str) -> list[tuple[datetime, float]]:
    if ticker == "USDCAD=X":
        return _series(1.35)
    if ticker == "AC.TO":
        return _series(20.0)
    return _series(75.0)  # SPY benchmark + US names (e.g. ARKK)


def test_cad_name_market_value_is_price_times_shares() -> None:
    uc = HoldingsRiskAssessmentUseCase(_provider, _FakeNarrator())
    report = uc.execute(
        [Holding("AC.TO", 30.0, 556.2, "FHSA")],
        datetime(2024, 1, 1, tzinfo=timezone.utc),
        datetime(2024, 9, 16, tzinfo=timezone.utc),
    )
    p = report["positions"][0]
    assert p.quantity == 30.0
    assert p.market_value_cad == 30.0 * 20.0  # fx 1.0 for .TO


def test_usd_name_market_value_converted_via_usdcad() -> None:
    uc = HoldingsRiskAssessmentUseCase(_provider, _FakeNarrator())
    report = uc.execute(
        [Holding("ARKK", 12.0, 1355.87, "FHSA")],
        datetime(2024, 1, 1, tzinfo=timezone.utc),
        datetime(2024, 9, 16, tzinfo=timezone.utc),
    )
    p = report["positions"][0]
    assert p.market_value_cad == 12.0 * 75.0 * 1.35


def test_fx_unavailable_yields_none_not_silent_native() -> None:
    def no_fx(ticker: str) -> list[tuple[datetime, float]]:
        if ticker == "USDCAD=X":
            return []
        return _series(75.0)

    uc = HoldingsRiskAssessmentUseCase(no_fx, _FakeNarrator())
    report = uc.execute(
        [Holding("ARKK", 12.0, 1355.87, "FHSA")],
        datetime(2024, 1, 1, tzinfo=timezone.utc),
        datetime(2024, 9, 16, tzinfo=timezone.utc),
    )
    assert report["positions"][0].market_value_cad is None  # fail loud downstream
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/application/test_holdings_risk_cad.py -v`
Expected: FAIL — `TypeError`/`AttributeError`: PositionRisk has no `quantity`

- [ ] **Step 3: Extend `PositionRisk` in `domain/models.py`**

Add two DEFAULTED fields at the END of the dataclass (after `why: str`, before `__post_init__`) so every existing constructor call keeps working:

```python
    quantity: float = 0.0
    market_value_cad: float | None = None  # None = FX/price unavailable, fail loud
```

- [ ] **Step 4: Plumb through `application/holdings_risk.py`**

In `execute()` (currently `holdings_risk.py:63`), before the holdings loop add:

```python
        fx_series = self._prices("USDCAD=X")
        usdcad: float | None = fx_series[-1][1] if fx_series else None
```

Add a helper method on the class:

```python
    def _market_value_cad(
        self, ticker: str, price: float, shares: float, usdcad: float | None
    ) -> float | None:
        """CAD market value via suffix-inferred currency (mirrors
        holdings_reader._to_yf): .TO/.V are CAD-native, everything else USD.
        Missing FX -> None (never silently native currency — spec v4)."""
        if ticker.endswith((".TO", ".V")):
            return price * shares
        if usdcad is None:
            return None
        return price * shares * usdcad
```

In the `PositionRisk(...)` construction (currently lines 126-143) add:

```python
                    quantity=h.shares,
                    market_value_cad=self._market_value_cad(
                        h.ticker, price, h.shares, usdcad
                    ),
```

In `_insufficient()` (lines 146-162) add:

```python
            quantity=h.shares,
            market_value_cad=None,
```

- [ ] **Step 5: Run tests — new file + existing suite**

Run: `pytest tests/application/test_holdings_risk_cad.py tests/ -x -q`
Expected: new tests PASS; zero regressions (defaulted fields keep old constructors valid).

- [ ] **Step 6: Commit**

```bash
git add domain/models.py application/holdings_risk.py tests/application/test_holdings_risk_cad.py
git commit -m "feat: PositionRisk carries quantity + CAD market value via USDCAD=X provider (Unit C)"
```

---

### Task 5: Log rows carry quantity + market_value_cad (CLI holdings-risk)

**Files:**
- Modify: `application/cli.py:2114-2126` (row construction in `holdings_risk`)
- Test: extend `tests/application/test_holdings_risk_cad.py`

- [ ] **Step 1: Write the failing test (append to test file)**

```python
def test_logged_rows_carry_quantity_and_cad_value(tmp_path) -> None:
    import json

    from click.testing import CliRunner

    from application import cli as cli_mod

    csv_path = tmp_path / "holdings.csv"
    csv_path.write_text(
        "Symbol,Exchange,Quantity,Book Value (CAD),Account Type\n"
        "AC,TSX,30,556.2,FHSA\n"
    )
    log_path = tmp_path / "log.jsonl"
    out_path = tmp_path / "detail.txt"

    runner = CliRunner()
    # monkeypatch-free: patch the price loader used inside the command
    import application.price_returns as pr

    orig = pr.load_price_series
    pr.load_price_series = lambda t, s, e: _provider(t)  # type: ignore[assignment]
    try:
        result = runner.invoke(
            cli_mod.cli,
            [
                "holdings-risk",
                "--holdings", str(csv_path),
                "--out", str(out_path),
                "--log", str(log_path),
            ],
        )
    finally:
        pr.load_price_series = orig  # type: ignore[assignment]
    assert result.exit_code == 0, result.output
    row = json.loads(log_path.read_text().splitlines()[0])
    assert row["quantity"] == 30.0
    assert row["market_value_cad"] == 600.0  # 30 * 20.0, .TO so fx 1.0
```

NOTE for implementer: `holdings_risk` imports `load_price_series` inside the
function body (`from application.price_returns import load_price_series` at
cli.py:2072), so patch `application.price_returns.load_price_series` (the
module attribute), as above. If the in-function import binds before the patch
in your test run, use pytest `monkeypatch.setattr("application.price_returns.load_price_series", ...)`
at module scope instead — same approach as `tests/application/test_cli_insider.py`.

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/application/test_holdings_risk_cad.py::test_logged_rows_carry_quantity_and_cad_value -v`
Expected: FAIL — `KeyError: 'quantity'`

- [ ] **Step 3: Extend the row dict at cli.py:2114-2126**

```python
    append_assessments(
        log,
        [
            {
                "ticker": p.ticker,
                "verdict": p.verdict.value,
                "price": p.price,
                "trend_health": p.trend_health,
                "as_of": now_iso,
                "quantity": p.quantity,
                "market_value_cad": p.market_value_cad,
            }
            for p in positions
        ],
    )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/application/test_holdings_risk_cad.py -v`
Expected: ALL PASS

- [ ] **Step 5: Commit**

```bash
git add application/cli.py tests/application/test_holdings_risk_cad.py
git commit -m "feat: discipline log rows carry quantity + market_value_cad (Unit C)"
```

---

### Task 6: Adherence use case (snapshots, matching, idempotent log, summary)

**Files:**
- Create: `application/adherence.py`
- Test: `tests/application/test_adherence_use_case.py`

- [ ] **Step 1: Write the failing tests**

```python
"""tests/application/test_adherence_use_case.py

Fixture story: AC.TO flagged REDUCE on Jun 13 with qty 100 @ 5000 CAD.
Week 2 (Jun 20): user sold to 40 (cut 0.6 >= f -> FOLLOWED).
XYZ flagged REDUCE Jun 13, never sold -> IGNORED; price falls 10% over 21d.
Discretionary trade: NEW position NEW1 on Jun 20 (no flag) -> throttle input.
"""
import json
from datetime import date, datetime, timedelta

from application.adherence import run_adherence_report


def _row(
    ticker: str, verdict: str, as_of: str, qty: float, mv: float
) -> dict[str, object]:
    return {
        "ticker": ticker,
        "verdict": verdict,
        "price": 50.0,
        "trend_health": -2.5,
        "as_of": as_of,
        "quantity": qty,
        "market_value_cad": mv,
    }


W1 = "2026-06-13T09:00:00+00:00"
W2 = "2026-06-20T09:00:00+00:00"


def _log_rows() -> list[dict[str, object]]:
    return [
        _row("AC.TO", "REDUCE", W1, 100.0, 5000.0),
        _row("XYZ.TO", "REDUCE", W1, 50.0, 5000.0),
        _row("AC.TO", "HOLD", W2, 40.0, 2000.0),
        _row("XYZ.TO", "REDUCE", W2, 50.0, 4500.0),  # re-flag: suppressed
        _row("NEW1.TO", "HOLD", W2, 10.0, 1000.0),  # discretionary NEW
    ]


def _falling_provider(ticker: str) -> list[tuple[datetime, float]]:
    # 100 -> 90 linearly over 30 days from Jun 13 (r_21d = -0.07 for XYZ check
    # is fine; exactness asserted via gap sign, not magnitude)
    start = datetime(2026, 6, 13)
    return [
        (start + timedelta(days=i), 100.0 - i * (10.0 / 30.0)) for i in range(40)
    ]


def _write_log(path, rows) -> None:
    with open(path, "w") as fh:
        for r in rows:
            fh.write(json.dumps(r) + "\n")


def test_report_end_to_end(tmp_path) -> None:
    log = tmp_path / "discipline_log.jsonl"
    adh = tmp_path / "adherence_log.jsonl"
    cash = tmp_path / "cash.json"
    _write_log(log, _log_rows())
    cash.write_text(json.dumps({"cash_cad": 500.0, "as_of": "2026-06-18"}))

    summary = run_adherence_report(
        log_path=str(log),
        adherence_log_path=str(adh),
        cash_config_path=str(cash),
        price_provider=_falling_provider,
        today=date(2026, 7, 10),  # 27d after W1 -> obligations resolvable
    )

    # snapshots: 2 dates
    assert summary["n_snapshots"] == 2
    # trades: AC.TO SELL (tool-matched), NEW1.TO NEW (discretionary)
    actions = {(t["ticker"], t["action"]) for t in summary["trades"]}
    assert ("AC.TO", "SELL") in actions
    assert ("NEW1.TO", "NEW") in actions
    # throttle counts ONLY discretionary
    assert summary["throttle"]["n_discretionary"] == 1
    assert summary["throttle"]["verdict"] == "OK"
    # buffer: 500 / (500 + 7500 latest pv) ~ 6.25% >= 5%
    assert summary["buffer"]["verdict"] == "OK"
    # adherence: AC.TO FOLLOWED (cut 0.6), XYZ.TO IGNORED with positive gap
    by_ticker = {r["ticker"]: r for r in summary["adherence"]}
    assert by_ticker["AC.TO"]["label"] == "FOLLOWED"
    assert by_ticker["AC.TO"]["gap_cad"] == 0.0
    assert by_ticker["XYZ.TO"]["label"] == "IGNORED"
    assert by_ticker["XYZ.TO"]["gap_cad"] > 0.0
    # one obligation per ticker despite XYZ re-flag
    assert len(summary["adherence"]) == 2
    # disclosure fields exist
    assert "skipped_unresolved" in summary
    assert "cumulative_gap_bps" in summary and "annualized_gap_bps" in summary


def test_rerun_is_idempotent(tmp_path) -> None:
    log = tmp_path / "discipline_log.jsonl"
    adh = tmp_path / "adherence_log.jsonl"
    cash = tmp_path / "cash.json"
    _write_log(log, _log_rows())
    cash.write_text(json.dumps({"cash_cad": 500.0, "as_of": "2026-06-18"}))

    for _ in range(3):
        run_adherence_report(
            log_path=str(log),
            adherence_log_path=str(adh),
            cash_config_path=str(cash),
            price_provider=_falling_provider,
            today=date(2026, 7, 10),
        )
    lines = adh.read_text().splitlines()
    keys = [
        (json.loads(ln)["ticker"], json.loads(ln)["flag_date"]) for ln in lines
    ]
    assert len(keys) == len(set(keys))  # no duplicate (ticker, flag_date)


def test_legacy_rows_without_quantity_no_baseline(tmp_path) -> None:
    log = tmp_path / "discipline_log.jsonl"
    legacy = [
        {"ticker": "AC.TO", "verdict": "REDUCE", "price": 20.0,
         "trend_health": -2.0, "as_of": W1}
    ]
    _write_log(log, legacy)
    summary = run_adherence_report(
        log_path=str(log),
        adherence_log_path=str(tmp_path / "adh.jsonl"),
        cash_config_path=str(tmp_path / "nope.json"),
        price_provider=_falling_provider,
        today=date(2026, 7, 10),
    )
    assert summary["status"] == "NO_BASELINE"
    assert summary["buffer"]["verdict"] == "STALE_CASH"  # missing cash.json -> loud


def test_missing_cash_config_is_stale_not_ok(tmp_path) -> None:
    log = tmp_path / "discipline_log.jsonl"
    _write_log(log, _log_rows())
    summary = run_adherence_report(
        log_path=str(log),
        adherence_log_path=str(tmp_path / "adh.jsonl"),
        cash_config_path=str(tmp_path / "missing.json"),
        price_provider=_falling_provider,
        today=date(2026, 7, 10),
    )
    assert summary["buffer"]["verdict"] == "STALE_CASH"


def test_same_day_rerun_keeps_latest(tmp_path) -> None:
    log = tmp_path / "discipline_log.jsonl"
    rows = _log_rows() + [
        _row("AC.TO", "HOLD", "2026-06-20T15:00:00+00:00", 41.0, 2050.0)
    ]  # second run same day, later timestamp -> wins
    _write_log(log, rows)
    summary = run_adherence_report(
        log_path=str(log),
        adherence_log_path=str(tmp_path / "adh.jsonl"),
        cash_config_path=str(tmp_path / "missing.json"),
        price_provider=_falling_provider,
        today=date(2026, 7, 10),
    )
    # AC.TO June-20 qty must come from the 15:00 run (41), not 09:00 (40)
    snap = summary["latest_snapshot"]
    assert snap["AC.TO"] == 41.0
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/application/test_adherence_use_case.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'application.adherence'`

- [ ] **Step 3: Write `application/adherence.py`**

```python
"""Unit C weekly adherence report: holdings-diff trades, discretionary
throttle, CAD cash buffer, obligation matching + 21d counterfactual gap.
Appends idempotently to a gitignored adherence_log.jsonl. PRIVACY: all inputs
and outputs live under data/personal/. Spec:
docs/superpowers/specs/2026-06-10-unit-c-adherence-design.md (v4)."""

from __future__ import annotations

import json
import os
from datetime import date, datetime, timedelta
from typing import Any, Callable

from application.discipline_log import _price_on_or_after, read_assessments
from domain.adherence import (
    CANONICAL_CUT_FRACTION,
    HORIZON_DAYS,
    DetectedTrade,
    TradeAction,
    actual_cut_fraction,
    adherence_label,
    annualize_bps,
    build_obligations,
    cash_buffer_check,
    diff_holdings,
    gap_bps,
    gap_cad,
    throttle_check,
)

PriceProvider = Callable[[str], list[tuple[datetime, float]]]


def _date_of(as_of: str) -> date:
    return datetime.fromisoformat(as_of).date()


def _snapshots(
    rows: list[dict[str, Any]],
) -> dict[date, list[dict[str, Any]]]:
    """Group rows by as_of DATE (calibration_readiness convention). Same-day
    re-runs: keep only rows from the max as_of timestamp on that date."""
    by_date: dict[date, dict[str, list[dict[str, Any]]]] = {}
    for r in rows:
        if r.get("quantity") is None:  # legacy rows: pre-Unit-C, no baseline
            continue
        d = _date_of(str(r["as_of"]))
        by_date.setdefault(d, {}).setdefault(str(r["as_of"]), []).append(r)
    return {
        d: runs[max(runs)] for d, runs in by_date.items()
    }


def _read_cash(path: str) -> tuple[float, date] | None:
    if not os.path.exists(path):
        return None
    with open(path) as fh:
        cfg = json.load(fh)
    return float(cfg["cash_cad"]), date.fromisoformat(str(cfg["as_of"]))


def _existing_keys(adherence_log_path: str) -> set[tuple[str, str]]:
    if not os.path.exists(adherence_log_path):
        return set()
    keys: set[tuple[str, str]] = set()
    with open(adherence_log_path) as fh:
        for line in fh:
            line = line.strip()
            if line:
                rec = json.loads(line)
                keys.add((str(rec["ticker"]), str(rec["flag_date"])))
    return keys


def run_adherence_report(
    log_path: str,
    adherence_log_path: str,
    cash_config_path: str,
    price_provider: PriceProvider,
    today: date,
    horizon_days: int = HORIZON_DAYS,
) -> dict[str, Any]:
    rows = read_assessments(log_path)
    snaps = _snapshots(rows)
    dates = sorted(snaps)

    summary: dict[str, Any] = {
        "status": "OK",
        "n_snapshots": len(dates),
        "trades": [],
        "adherence": [],
        "skipped_unresolved": [],
    }

    # --- cash buffer (always computed; loud when inputs missing) ---
    latest_qty: dict[str, float] = {}
    latest_pv: float | None = None
    if dates:
        latest_rows = snaps[dates[-1]]
        latest_qty = {str(r["ticker"]): float(r["quantity"]) for r in latest_rows}
        mvs = [r.get("market_value_cad") for r in latest_rows]
        latest_pv = (
            sum(float(v) for v in mvs if v is not None) if any(
                v is not None for v in mvs
            ) else None
        )
    summary["latest_snapshot"] = latest_qty
    cash = _read_cash(cash_config_path)
    if cash is None:
        buffer = cash_buffer_check(0.0, None, today, today)
    else:
        buffer = cash_buffer_check(cash[0], latest_pv, cash[1], today)
    summary["buffer"] = {
        "verdict": buffer.verdict.value,
        "cash_pct": buffer.cash_pct,
    }

    if len(dates) < 2:
        summary["status"] = "NO_BASELINE"
        summary["throttle"] = {"verdict": "OK", "n_discretionary": 0}
        return summary

    # --- trades from consecutive snapshot diffs ---
    trades: list[DetectedTrade] = []
    for prev_d, curr_d in zip(dates, dates[1:]):
        prev_q = {str(r["ticker"]): float(r["quantity"]) for r in snaps[prev_d]}
        curr_q = {str(r["ticker"]): float(r["quantity"]) for r in snaps[curr_d]}
        trades.extend(diff_holdings(prev_q, curr_q, curr_d))
    summary["trades"] = [
        {
            "ticker": t.ticker,
            "action": t.action.value,
            "qty_before": t.qty_before,
            "qty_after": t.qty_after,
            "week_of": t.week_of.isoformat(),
        }
        for t in trades
    ]

    # --- obligations (one per ticker+verdict per horizon) ---
    flag_rows = [
        {
            "ticker": r["ticker"],
            "verdict": r["verdict"],
            "as_of_date": _date_of(str(r["as_of"])),
            "quantity": r["quantity"],
            "market_value_cad": r["market_value_cad"],
        }
        for d in dates
        for r in snaps[d]
        if r.get("verdict") in ("REDUCE", "TRIM")
        and r.get("market_value_cad") is not None
    ]
    obligations = build_obligations(flag_rows, horizon_days)

    # --- throttle on DISCRETIONARY trades of the latest diff window ---
    open_tickers = {
        o.ticker
        for o in obligations
        if (dates[-1] - o.flag_date).days <= horizon_days
    }
    latest_trades = [t for t in trades if t.week_of == dates[-1]]
    discretionary = [
        t
        for t in latest_trades
        if not (
            t.action in (TradeAction.SELL, TradeAction.EXIT)
            and t.ticker in open_tickers
        )
        and t.action is not TradeAction.SUSPECTED_SPLIT
    ]
    weeks = max(1.0, (dates[-1] - dates[-2]).days / 7.0)
    throttle = throttle_check(len(discretionary), weeks)
    summary["throttle"] = {
        "verdict": throttle.verdict.value,
        "trades_per_week": throttle.trades_per_week,
        "n_discretionary": len(discretionary),
        "note": "net weekly position changes; intra-week round trips invisible "
        "(lower bound)",
    }

    # --- adherence + gap for obligations whose horizon elapsed ---
    pv_by_date: dict[date, float] = {}
    for d in dates:
        mvs2 = [r.get("market_value_cad") for r in snaps[d]]
        vals = [float(v) for v in mvs2 if v is not None]
        if vals:
            pv_by_date[d] = sum(vals)

    existing = _existing_keys(adherence_log_path)
    new_records: list[dict[str, Any]] = []
    cumulative_reduce_bps = 0.0
    cumulative_trim_bps = 0.0
    for ob in obligations:
        if (today - ob.flag_date).days < horizon_days:
            continue  # still open, resolve later
        window_end = ob.flag_date + timedelta(days=horizon_days)
        later_qs = [
            float(
                next(
                    (
                        r["quantity"]
                        for r in snaps[d]
                        if str(r["ticker"]) == ob.ticker
                    ),
                    0.0,
                )
            )
            for d in dates
            if ob.flag_date < d <= window_end
        ]
        cut = actual_cut_fraction(ob.quantity, later_qs)
        label = adherence_label(cut)
        series = [
            (dt.replace(tzinfo=None), c) for dt, c in price_provider(ob.ticker)
        ]
        flag_dt = datetime(ob.flag_date.year, ob.flag_date.month, ob.flag_date.day)
        entry = _price_on_or_after(series, flag_dt)
        later = _price_on_or_after(series, flag_dt + timedelta(days=horizon_days))
        if entry is None or later is None or entry <= 0:
            summary["skipped_unresolved"].append(ob.ticker)
            continue
        r_21d = later / entry - 1.0
        g = gap_cad(ob.market_value_cad, cut, r_21d)
        pv = pv_by_date.get(ob.flag_date, 0.0)
        g_bps = gap_bps(g, pv)
        if ob.verdict == "REDUCE":
            cumulative_reduce_bps += g_bps
        else:
            cumulative_trim_bps += g_bps
        record = {
            "ticker": ob.ticker,
            "verdict": ob.verdict,
            "flag_date": ob.flag_date.isoformat(),
            "actual_cut_fraction": cut,
            "label": label.value,
            "r_21d": r_21d,
            "gap_cad": g,
            "gap_bps": g_bps,
            "f": CANONICAL_CUT_FRACTION,
        }
        summary["adherence"].append(record)
        if (ob.ticker, ob.flag_date.isoformat()) not in existing:
            new_records.append(record)

    if new_records:
        os.makedirs(os.path.dirname(adherence_log_path) or ".", exist_ok=True)
        with open(adherence_log_path, "a") as fh:
            for rec in new_records:
                fh.write(json.dumps(rec) + "\n")

    days_observed = max(1.0, float((dates[-1] - dates[0]).days))
    summary["cumulative_gap_bps"] = cumulative_reduce_bps  # REDUCE-only headline
    summary["trim_gap_bps"] = cumulative_trim_bps  # informational (sizing advice)
    summary["annualized_gap_bps"] = annualize_bps(
        cumulative_reduce_bps, days_observed
    )
    summary["days_observed"] = days_observed
    return summary
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/application/test_adherence_use_case.py -v`
Expected: ALL PASS. Debug notes if not:
- `test_report_end_to_end` buffer: latest pv = 2000 + 4500 + 1000 = 7500; 500/8000 = 6.25% ≥ 5% → OK.
- XYZ.TO obligation dates: W1 flag + W2 re-flag 7d later < 21d → suppressed (1 obligation).
- AC.TO: HOLD row at W2 is the snapshot, qty 40; cut = (100−40)/100 = 0.6 ≥ 0.5 → FOLLOWED.

- [ ] **Step 5: Commit**

```bash
git add application/adherence.py tests/application/test_adherence_use_case.py
git commit -m "feat: adherence report use case — diffs, throttle, buffer, idempotent gap log (Unit C)"
```

---

### Task 7: CLI `adherence-report` subcommand + end-to-end test

**Files:**
- Modify: `application/cli.py` (append new command after `discipline-calibration-status`, ~line 2250)
- Test: `tests/application/test_cli_adherence.py`

- [ ] **Step 1: Write the failing test**

```python
"""tests/application/test_cli_adherence.py — end-to-end CLI pattern, mirrors
tests/application/test_cli_insider.py (CliRunner + monkeypatch + tmp_path)."""
import json
from datetime import datetime, timedelta

from click.testing import CliRunner

from application import cli as cli_mod


def _provider(ticker: str) -> list[tuple[datetime, float]]:
    start = datetime(2026, 6, 13)
    return [(start + timedelta(days=i), 100.0 - i * 0.3) for i in range(40)]


def test_adherence_report_end_to_end(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(
        "application.price_returns.load_price_series",
        lambda t, s, e: _provider(t),
    )
    log = tmp_path / "discipline_log.jsonl"
    rows = [
        {"ticker": "XYZ.TO", "verdict": "REDUCE", "price": 100.0,
         "trend_health": -2.5, "as_of": "2026-06-13T09:00:00+00:00",
         "quantity": 50.0, "market_value_cad": 5000.0},
        {"ticker": "XYZ.TO", "verdict": "REDUCE", "price": 95.0,
         "trend_health": -2.5, "as_of": "2026-06-20T09:00:00+00:00",
         "quantity": 50.0, "market_value_cad": 4750.0},
    ]
    log.write_text("\n".join(json.dumps(r) for r in rows) + "\n")
    cash = tmp_path / "cash.json"
    cash.write_text(json.dumps({"cash_cad": 1000.0, "as_of": "2026-07-08"}))
    adh = tmp_path / "adherence_log.jsonl"

    result = CliRunner().invoke(
        cli_mod.cli,
        [
            "adherence-report",
            "--log", str(log),
            "--cash-config", str(cash),
            "--adherence-log", str(adh),
            "--today", "2026-07-10",
        ],
    )
    assert result.exit_code == 0, result.output
    assert "IGNORED" in result.output  # XYZ never sold
    assert "gap" in result.output.lower()
    assert "skipped_unresolved" in result.output or "skipped" in result.output.lower()
    assert adh.exists()  # record appended
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/application/test_cli_adherence.py -v`
Expected: FAIL — `Error: No such command 'adherence-report'` (exit_code 2)

- [ ] **Step 3: Add the command to `application/cli.py`** (after `discipline_calibration_status`)

```python
@cli.command("adherence-report")
@click.option("--log", default="data/personal/discipline_log.jsonl", show_default=True)
@click.option(
    "--cash-config",
    default="data/personal/cash.json",
    show_default=True,
    help='Gitignored JSON: {"cash_cad": 1234.56, "as_of": "YYYY-MM-DD"}. '
    "Update on material change; >28d stale flags STALE_CASH.",
)
@click.option(
    "--adherence-log",
    default="data/personal/adherence_log.jsonl",
    show_default=True,
    help="Append-only adherence records, idempotent by (ticker, flag_date).",
)
@click.option("--today", default=None, help="Override today (ISO date) for tests.")
def adherence_report(
    log: str, cash_config: str, adherence_log: str, today: str | None
) -> None:
    """Weekly Unit C report: detected trades (holdings-diff, lower bound),
    discretionary-trade throttle, CAD cash-buffer floor, and per-flag adherence
    with 21d counterfactual gap (f=0.5). Advisory only (L0). Descriptive,
    underpowered by design — no significance claims (spec Interpretation limits).
    """
    from datetime import date, datetime, timezone

    from application.adherence import run_adherence_report
    from application.price_returns import load_price_series

    start_dt = datetime(2018, 1, 1, tzinfo=timezone.utc)
    end_dt = datetime.now(timezone.utc)

    def provider(ticker: str) -> list[tuple[datetime, float]]:
        return load_price_series(ticker, start_dt, end_dt)

    today_d = date.fromisoformat(today) if today else end_dt.date()
    s = run_adherence_report(
        log_path=log,
        adherence_log_path=adherence_log,
        cash_config_path=cash_config,
        price_provider=provider,
        today=today_d,
    )
    click.echo(f"Adherence report (today {today_d.isoformat()})  status={s['status']}")
    click.echo(
        f"  snapshots: {s['n_snapshots']}  trades detected: {len(s['trades'])}"
        "  (net weekly position changes — lower bound)"
    )
    for t in s["trades"]:
        click.echo(
            f"    {t['week_of']}  {t['ticker']:10} {t['action']:16} "
            f"{t['qty_before']:.1f} -> {t['qty_after']:.1f}"
        )
    th = s["throttle"]
    click.echo(
        f"  THROTTLE: {th['verdict']}  discretionary={th['n_discretionary']}"
    )
    b = s["buffer"]
    pct = f"{b['cash_pct']:.1%}" if b["cash_pct"] is not None else "n/a"
    click.echo(f"  CASH BUFFER: {b['verdict']}  cash_pct={pct}")
    for r in s["adherence"]:
        click.echo(
            f"  {r['flag_date']}  {r['ticker']:10} {r['verdict']:7} "
            f"{r['label']:9} cut={r['actual_cut_fraction']:.0%} "
            f"gap={r['gap_cad']:+.0f} CAD ({r['gap_bps']:+.1f} bps)"
        )
    skipped = s["skipped_unresolved"]
    click.echo(
        f"  skipped_unresolved: {len(skipped)} {skipped} — flags excluded for "
        "missing 21d prices (incl. delistings); gap is conservative."
    )
    if "cumulative_gap_bps" in s:
        click.echo(
            f"  GAP (REDUCE-only headline): {s['cumulative_gap_bps']:+.1f} bps "
            f"over {s['days_observed']:.0f}d; annualized "
            f"{s['annualized_gap_bps']:+.1f} bps/yr "
            "(context: literature disposition effect ~848 bps/yr; point estimate "
            "only, no significance claim)"
        )
        click.echo(f"  TRIM gap (informational, sizing advice): {s['trim_gap_bps']:+.1f} bps")
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/application/test_cli_adherence.py -v`
Expected: PASS

- [ ] **Step 5: Run full suite + commit**

Run: `pytest tests/ -x -q`
Expected: all green.

```bash
git add application/cli.py tests/application/test_cli_adherence.py
git commit -m "feat: adherence-report CLI command (Unit C)"
```

---

### Task 8: Saturday cron step 4 + docs

**Files:**
- Modify: `scripts/discipline_weekly_review.sh`
- Modify: `docs/STATUS.md` (session end)

- [ ] **Step 1: Add step 4 to the script** (inside the existing `{ ... } >> "$OUT" 2>&1` block, after step 3)

```bash
  echo "--- 4. adherence report (Unit C: trades, throttle, buffer, gap) ---"
  "$PYTHON" -m application.cli adherence-report
```

Also update the header comment block (lines 2-13) — append:

```bash
#   4. adherence-report -> holdings-diff trades, discretionary throttle, cash
#      buffer, 21d counterfactual adherence gap (Unit C, spec 2026-06-10).
```

- [ ] **Step 2: Smoke-test the script syntax**

Run: `bash -n scripts/discipline_weekly_review.sh`
Expected: no output (syntax OK). Do NOT execute the full script (hits yfinance).

- [ ] **Step 3: Create cash.json locally (NOT committed — data/personal/ is gitignored)**

Ask the user for the current cash balance, or create a placeholder they must edit:

```bash
test -f data/personal/cash.json || printf '{"cash_cad": 0.0, "as_of": "%s"}\n' "$(date +%Y-%m-%d)" > data/personal/cash.json
echo "EDIT data/personal/cash.json with real cash balance"
```

- [ ] **Step 4: Verify gitignore covers new files**

Run: `git check-ignore data/personal/cash.json data/personal/adherence_log.jsonl && echo IGNORED-OK`
Expected: both paths printed + `IGNORED-OK`.

- [ ] **Step 5: Full check + commit**

Run: `pytest tests/ -q` (and `make check` if venv hardening has landed)
Expected: green.

```bash
git add scripts/discipline_weekly_review.sh
git commit -m "feat: Saturday review step 4 — adherence report (Unit C)"
```

- [ ] **Step 6: Overwrite docs/STATUS.md** (session end; keep ~40 lines: Unit C shipped, next = hardening sprint then dashboard; preserve hard caveats + pointers)

```bash
git add docs/STATUS.md
git commit -m "docs: STATUS — Unit C shipped"
```

---

## Plan self-review (done at write time)

- **Spec coverage:** diff/split/DRIP → T1; throttle + buffer → T2 (+T6 exemption wiring); obligations/labels/gap/bps/annualization → T3; CAD + FX + PositionRisk → T4; log rows → T5; snapshots/idempotency/disclosure → T6; CLI → T7; cron + cash.json + gitignore → T8. Interpretation-limits language lives in the CLI output (T7). No uncovered spec section.
- **Type consistency:** `diff_holdings(prev, curr, week_of, ...)`, `gap_cad(flag_value_cad, cut, r_21d, f)`, `build_obligations(flag_rows, horizon_days)` used identically across T1/T3/T6. `PositionRisk.quantity/market_value_cad` (T4) match row keys (T5) and reader `.get` usage (T6).
- **Known risk:** mypy not in shared venv (STATUS caveat) — plan says run tests regardless, mypy when hardening lands. Pre-commit's mypy hook skips when files unchanged in its env; if it blocks, fix types, never `--no-verify`.
