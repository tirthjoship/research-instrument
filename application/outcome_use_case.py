"""OutcomeTrackingUseCase — orchestrates trade logging and outcome evaluation."""

from __future__ import annotations

import uuid
from typing import Any

from loguru import logger

from domain.outcome import TrackedTrade, TradeAction, TradeOutcome
from domain.outcome_service import (
    compute_outcome,
    compute_signal_performance,
    generate_report_card,
)


class OutcomeTrackingUseCase:
    """Records trades and computes performance outcomes.

    Args:
        store: Any object implementing save_trade, get_trades,
               save_outcome, get_outcomes.
    """

    def __init__(self, store: Any) -> None:
        self._store = store

    # ------------------------------------------------------------------
    # Buy / Sell recording
    # ------------------------------------------------------------------

    def record_buy(
        self,
        ticker: str,
        price: float,
        quantity: int,
        trade_date: str,
        conviction: float = 0.0,
        signals: list[str] | None = None,
        opportunity_card_id: str = "",
        notes: str = "",
    ) -> TrackedTrade:
        """Record an opening BUY trade.

        Returns:
            The persisted TrackedTrade.
        """
        trade_id = str(uuid.uuid4())[:8]
        trade = TrackedTrade(
            trade_id=trade_id,
            ticker=ticker,
            action=TradeAction.BUY,
            price=price,
            quantity=quantity,
            trade_date=trade_date,
            conviction_at_trade=conviction,
            signals_at_trade=signals if signals is not None else [],
            opportunity_card_id=opportunity_card_id,
            notes=notes,
        )
        self._store.save_trade(trade)
        logger.info("Recorded BUY trade {} for {} @ {}", trade_id, ticker, price)
        return trade

    def record_sell(
        self,
        ticker: str,
        price: float,
        quantity: int,
        trade_date: str,
        notes: str = "",
    ) -> tuple[TradeOutcome, TrackedTrade] | None:
        """Record a closing SELL trade and compute outcome.

        Finds the most recent BUY for the ticker.  If none exists returns None.

        Returns:
            (TradeOutcome, sell TrackedTrade) or None if no prior buy found.
        """
        all_trades: list[TrackedTrade] = self._store.get_trades()
        buys = [
            t for t in all_trades if t.ticker == ticker and t.action == TradeAction.BUY
        ]
        if not buys:
            logger.warning("No open BUY found for {} — sell ignored", ticker)
            return None

        # Most recent buy by trade_date, then by insertion order (last)
        buy = sorted(buys, key=lambda t: t.trade_date)[-1]

        trade_id = str(uuid.uuid4())[:8]
        sell_trade = TrackedTrade(
            trade_id=trade_id,
            ticker=ticker,
            action=TradeAction.SELL,
            price=price,
            quantity=quantity,
            trade_date=trade_date,
            conviction_at_trade=0.0,
            signals_at_trade=[],
            notes=notes,
        )
        self._store.save_trade(sell_trade)

        outcome = compute_outcome(buy, sell_trade)
        self._store.save_outcome(outcome)

        logger.info(
            "Recorded SELL trade {} for {} @ {} — return {:.2f}%",
            trade_id,
            ticker,
            price,
            outcome.return_pct,
        )
        return outcome, sell_trade

    # ------------------------------------------------------------------
    # Reporting
    # ------------------------------------------------------------------

    def get_signal_report(self, month: str = "") -> str:
        """Generate a plain-text signal performance report card.

        Args:
            month: Optional period label (e.g. "2024-01").

        Returns:
            Formatted report string.
        """
        outcomes: list[TradeOutcome] = self._store.get_outcomes()
        performances = compute_signal_performance(outcomes)
        return generate_report_card(performances, month=month)

    def get_outcomes_summary(self) -> dict[str, Any]:
        """Summarise all completed outcomes.

        Returns:
            Dict with keys: total_trades, total_return, win_rate, avg_return_pct.
        """
        outcomes: list[TradeOutcome] = self._store.get_outcomes()
        if not outcomes:
            return {
                "total_trades": 0,
                "total_return": 0.0,
                "win_rate": 0.0,
                "avg_return_pct": 0.0,
            }

        total = len(outcomes)
        winners = sum(1 for o in outcomes if o.is_profitable)
        total_return = sum(o.return_dollar for o in outcomes)
        avg_return = sum(o.return_pct for o in outcomes) / total

        return {
            "total_trades": total,
            "total_return": total_return,
            "win_rate": (winners / total) * 100.0,
            "avg_return_pct": avg_return,
        }
