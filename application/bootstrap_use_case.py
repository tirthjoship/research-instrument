"""Historical Bootstrap Use Case — simulates past outcomes for cold-start learning.

Walks a date range in fixed steps, calls market data for buy and sell prices,
computes returns, and persists TradeOutcome records so the learning layer has
historical signal performance data before any live trades are made.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta
from typing import Any

from loguru import logger

from domain.outcome import TradeOutcome


class HistoricalBootstrapUseCase:
    """Simulate historical round-trip trades for cold-start learning.

    Args:
        market_data: Any object with get_signals(symbol, prediction_time,
            start_date, end_date) -> list[Signal].
        store: Any object with save_outcome(outcome) and get_outcomes(ticker).
        tickers: Universe of tickers to simulate.
    """

    def __init__(self, market_data: Any, store: Any, tickers: list[str]) -> None:
        self._market_data = market_data
        self._store = store
        self._tickers = tickers

    def run(
        self,
        start_date: datetime,
        end_date: datetime,
        horizon_days: int = 30,
        step_days: int = 30,
    ) -> list[TradeOutcome]:
        """Walk windows from start_date to end_date and generate TradeOutcome records.

        For each step window and each ticker:
        - Buy price = first signal price at window start.
        - Sell price = first signal price at window start + horizon_days.
        - Skips tickers with missing data silently.

        Returns:
            All generated TradeOutcome records (also persisted to store).
        """
        if not self._tickers:
            logger.info("bootstrap: no tickers configured, returning empty list")
            return []

        all_outcomes: list[TradeOutcome] = []
        window_start = start_date
        window_count = 0

        while window_start < end_date:
            window_sell = window_start + timedelta(days=horizon_days)
            window_count += 1
            logger.info(
                "bootstrap: window {}/{} — {} → {}",
                window_count,
                "?",
                window_start.date(),
                window_sell.date(),
            )

            for ticker in self._tickers:
                outcome = self._simulate_outcome(
                    ticker, window_start, window_sell, horizon_days
                )
                if outcome is not None:
                    all_outcomes.append(outcome)
                    self._store.save_trade_outcome(outcome)

            window_start += timedelta(days=step_days)

        logger.info(
            "bootstrap: complete — {} outcomes across {} tickers, {} windows",
            len(all_outcomes),
            len(self._tickers),
            window_count,
        )
        return all_outcomes

    def _simulate_outcome(
        self,
        ticker: str,
        buy_date: datetime,
        sell_date: datetime,
        horizon_days: int,
    ) -> TradeOutcome | None:
        """Simulate a single round-trip trade. Returns None if data is missing."""
        try:
            buy_signals = self._market_data.get_signals(ticker, buy_date)
            sell_signals = self._market_data.get_signals(ticker, sell_date)
        except Exception as exc:
            logger.warning("bootstrap: data fetch failed for {} — {}", ticker, exc)
            return None

        if not buy_signals or not sell_signals:
            logger.debug(
                "bootstrap: no signals for {} at {} or {}",
                ticker,
                buy_date.date(),
                sell_date.date(),
            )
            return None

        buy_price = buy_signals[0].price
        sell_price = sell_signals[0].price

        return_dollar = sell_price - buy_price
        return_pct = return_dollar / buy_price * 100.0

        trade_id_prefix = uuid.uuid4().hex[:8]
        return TradeOutcome(
            ticker=ticker,
            buy_trade_id=f"bootstrap-buy-{trade_id_prefix}",
            sell_trade_id=f"bootstrap-sell-{trade_id_prefix}",
            buy_price=buy_price,
            sell_price=sell_price,
            quantity=1,
            buy_date=buy_date.strftime("%Y-%m-%d"),
            sell_date=sell_date.strftime("%Y-%m-%d"),
            holding_days=horizon_days,
            return_pct=return_pct,
            return_dollar=return_dollar,
            signals_at_entry=["technical", "fundamental"],
            conviction_at_entry=0.5,
        )
