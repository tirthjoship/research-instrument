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
