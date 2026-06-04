"""Outcome tracking domain models.

Pure Python value objects — no external framework imports.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class TradeAction(str, Enum):
    """Action taken on a trade."""

    BUY = "BUY"
    SELL = "SELL"


@dataclass(frozen=True)
class TrackedTrade:
    """An immutable record of a single buy or sell trade.

    Attributes:
        trade_id: Unique identifier for this trade.
        ticker: Ticker symbol.
        action: BUY or SELL.
        price: Execution price per share (must be > 0).
        quantity: Number of shares traded (must be > 0).
        trade_date: Date of execution in YYYY-MM-DD format.
        conviction_at_trade: Conviction score at the time of the trade.
        signals_at_trade: List of signal names that were active at trade time.
        opportunity_card_id: ID of the opportunity card that triggered the trade (optional).
        notes: Free-form annotation (optional).
    """

    trade_id: str
    ticker: str
    action: TradeAction
    price: float
    quantity: int
    trade_date: str
    conviction_at_trade: float
    signals_at_trade: list[str]
    opportunity_card_id: str = ""
    notes: str = ""

    def __post_init__(self) -> None:
        if self.price <= 0:
            raise ValueError(f"price must be > 0, got {self.price}")
        if self.quantity <= 0:
            raise ValueError(f"quantity must be > 0, got {self.quantity}")

    @property
    def total_value(self) -> float:
        """Total dollar value of the trade (price × quantity)."""
        return self.price * self.quantity


@dataclass(frozen=True)
class TradeOutcome:
    """Immutable record of a completed round-trip trade (buy → sell).

    Attributes:
        ticker: Ticker symbol.
        buy_trade_id: ID of the opening TrackedTrade.
        sell_trade_id: ID of the closing TrackedTrade.
        buy_price: Price paid per share at entry.
        sell_price: Price received per share at exit.
        quantity: Number of shares in the round-trip.
        buy_date: Entry date in YYYY-MM-DD format.
        sell_date: Exit date in YYYY-MM-DD format.
        holding_days: Calendar days held.
        return_pct: Percentage return (positive = gain).
        return_dollar: Dollar return (positive = gain).
        signals_at_entry: Signal names that were active at entry.
        conviction_at_entry: Conviction score at entry.
    """

    ticker: str
    buy_trade_id: str
    sell_trade_id: str
    buy_price: float
    sell_price: float
    quantity: int
    buy_date: str
    sell_date: str
    holding_days: int
    return_pct: float
    return_dollar: float
    signals_at_entry: list[str]
    conviction_at_entry: float

    @property
    def is_profitable(self) -> bool:
        """True when the return percentage is positive."""
        return self.return_pct > 0


@dataclass(frozen=True)
class SignalPerformance:
    """Aggregated performance statistics for a single signal name.

    Attributes:
        signal_name: The signal identifier (e.g. "rsi_oversold").
        total_trades: Total number of trades where this signal was active.
        winning_trades: Count of profitable outcomes.
        losing_trades: Count of unprofitable outcomes.
        hit_rate: Percentage of winning trades (0–100).
        avg_return_pct: Mean return across all trades.
        avg_winning_return: Mean return on winning trades.
        avg_losing_return: Mean return on losing trades (typically negative).
    """

    signal_name: str
    total_trades: int
    winning_trades: int
    losing_trades: int
    hit_rate: float
    avg_return_pct: float
    avg_winning_return: float = 0.0
    avg_losing_return: float = 0.0

    @property
    def is_useful(self) -> bool:
        """True when the hit rate exceeds 50%."""
        return self.hit_rate > 50.0
