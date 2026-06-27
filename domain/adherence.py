"""domain/adherence.py — Unit C pure primitives (stdlib only).

Holdings-diff trade detection, discretionary-trade throttle, CAD cash-buffer
floor, one-obligation-per-ticker adherence matching, and the canonical
21d-counterfactual gap formula (f = 0.5). The deterministic
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
_SPLIT_FACTORS = (2.0, 3.0, 1.5)
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
    # Only forward splits (ratio > 1) are guarded: a forward split inflates
    # the logged share count against a split-adjusted price and fabricates a
    # phantom BUY (the corrupting case). Reverse splits (ratio < 1) collide
    # with ordinary 50% trims and merely fabricate a less-harmful SELL, so
    # share decreases are always SELL/EXIT — not guarded.
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


def adherence_label(cut: float, f: float = CANONICAL_CUT_FRACTION) -> AdherenceLabel:
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
