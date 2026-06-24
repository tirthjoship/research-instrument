"""Thin yfinance adapter implementing ResolverPricePort for SP5 gate resolution."""

from __future__ import annotations

from datetime import date, timedelta

import yfinance as yf


class YFinancePriceResolver:
    """Fetch historical closing prices via yfinance.

    Implements ResolverPricePort (structural duck-typing — no explicit import
    needed; mypy checks the Protocol at call sites).
    """

    def price_at(self, ticker: str, on: date) -> float:
        """Return the adjusted closing price for *ticker* on or before *on*.

        Fetches a 5-day window ending the day after *on* so weekends/holidays
        resolve cleanly to the last available trading day.

        Raises ValueError if no price data is found.
        """
        start = on - timedelta(days=4)
        end = on + timedelta(days=1)
        df = yf.download(
            ticker,
            start=start.strftime("%Y-%m-%d"),
            end=end.strftime("%Y-%m-%d"),
            auto_adjust=True,
            progress=False,
        )
        if df.empty:
            raise ValueError(f"No price data for {ticker} around {on}")

        # df["Close"] is a Series when a single ticker string is passed
        close_series = df[["Close"]].squeeze()
        mask = [d.date() <= on for d in close_series.index]
        filtered = close_series[mask]
        if filtered.empty:
            raise ValueError(f"No price for {ticker} on or before {on}")
        return float(filtered.iloc[-1])
