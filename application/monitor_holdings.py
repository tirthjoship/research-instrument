"""Monitor holdings use case — detect sell signals for portfolio positions."""

from __future__ import annotations

from datetime import datetime
from typing import Callable

from domain.models import Holding, SellSignal


class MonitorHoldingsUseCase:
    """Check all holdings for sell signals: stop-loss, sentiment, technical."""

    def __init__(
        self,
        holdings: object,  # HoldingsPort
        get_current_price: Callable[[str], float],
        stop_loss_threshold: float = -0.08,
        get_sentiment_score: Callable[[str], float] | None = None,
        get_technical_signal: Callable[[str], dict[str, float]] | None = None,
        sentiment_threshold: float = -0.5,
    ) -> None:
        self._holdings = holdings
        self._get_price = get_current_price
        self._stop_loss = stop_loss_threshold
        self._get_sentiment = get_sentiment_score
        self._get_technical = get_technical_signal
        self._sentiment_threshold = sentiment_threshold

    def execute(self, check_time: datetime) -> list[SellSignal]:
        """Check all holdings and return any triggered sell signals."""
        signals: list[SellSignal] = []
        holdings: list[Holding] = self._holdings.get_holdings()  # type: ignore[attr-defined]
        date_str = check_time.strftime("%Y-%m-%d")

        for holding in holdings:
            signals.extend(self._check_holding(holding, date_str))

        return signals

    def _check_holding(self, holding: Holding, date_str: str) -> list[SellSignal]:
        """Run all sell signal checks for a single holding."""
        signals: list[SellSignal] = []
        current_price = self._get_price(holding.symbol)

        # 1. Stop-loss check
        pct_change = (current_price / holding.purchase_price) - 1.0
        if pct_change <= self._stop_loss:
            signals.append(
                SellSignal(
                    symbol=holding.symbol,
                    signal_date=date_str,
                    signal_type="stop_loss",
                    urgency="immediate",
                    reasoning=f"Price dropped {pct_change:.1%} (threshold: {self._stop_loss:.1%})",
                    confidence=0.95,
                )
            )

        # 2. Negative sentiment check
        if self._get_sentiment is not None:
            score = self._get_sentiment(holding.symbol)
            if score <= self._sentiment_threshold:
                signals.append(
                    SellSignal(
                        symbol=holding.symbol,
                        signal_date=date_str,
                        signal_type="negative_sentiment",
                        urgency="this_week",
                        reasoning=f"Sentiment score {score:.2f} below threshold {self._sentiment_threshold}",
                        confidence=min(1.0, abs(score)),
                    )
                )

        # 3. Technical breakdown check
        if self._get_technical is not None:
            tech = self._get_technical(holding.symbol)
            price_vs_sma = tech.get("price_vs_sma20", 0.0)
            macd_hist = tech.get("macd_histogram", 0.0)
            if price_vs_sma < -0.02 and macd_hist < 0:
                signals.append(
                    SellSignal(
                        symbol=holding.symbol,
                        signal_date=date_str,
                        signal_type="technical_breakdown",
                        urgency="this_week",
                        reasoning=f"Price {price_vs_sma:.1%} below SMA20, MACD histogram negative ({macd_hist:.4f})",
                        confidence=0.7,
                    )
                )

        return signals
