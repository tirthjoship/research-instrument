"""Apply the validated trend/exit rules to current holdings (application, not
validation — see spec). Output is decision-support, not a forecast."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Callable

from domain.trend_rules import above_trend, atr, chandelier_stop, sma

PriceProvider = Callable[[str], list[tuple[datetime, float]]]


class PortfolioVerdictUseCase:
    def __init__(
        self,
        price_provider: PriceProvider,
        trend_window: int = 200,
        atr_window: int = 22,
        atr_mult: float = 3.0,
    ) -> None:
        self._prices = price_provider
        self._trend_window = trend_window
        self._atr_window = atr_window
        self._atr_mult = atr_mult

    def verdict_for(self, ticker: str) -> dict[str, Any]:
        series = self._prices(ticker)
        closes = [p for _, p in series]
        if len(closes) < self._trend_window:
            return {
                "ticker": ticker,
                "verdict": "INSUFFICIENT_DATA",
                "trend_intact": False,
                "trailing_stop": None,
            }
        price = closes[-1]
        trend = above_trend(price, sma(closes, self._trend_window))
        atr_v = atr(closes, closes, closes, self._atr_window)
        highest = max(closes[-self._trend_window :])
        stop = chandelier_stop(highest, atr_v, self._atr_mult) if atr_v else None
        if not trend:
            verdict = "EXIT"
        elif stop is not None and price <= stop:
            verdict = "TRIM"
        else:
            verdict = "HOLD"
        return {
            "ticker": ticker,
            "price": price,
            "verdict": verdict,
            "trend_intact": trend,
            "trailing_stop": stop,
            "why": _why(verdict, trend, price, stop),
        }


def _why(verdict: str, trend: bool, price: float, stop: float | None) -> str:
    if verdict == "EXIT":
        return "Below 200-day trend — discipline says exit, don't anchor."
    if verdict == "TRIM":
        return "In trend but breached trailing stop — trim/tighten."
    return (
        f"Trend intact; ride it, trailing stop at {stop:.2f}."
        if stop
        else "Trend intact."
    )
