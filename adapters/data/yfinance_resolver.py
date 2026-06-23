"""YFinance adapter for TickerResolverPort — resolves ticker → (company_name, sector)."""

from __future__ import annotations

from loguru import logger


class YFinanceResolver:
    """Implements TickerResolverPort via yfinance.Ticker.info."""

    def resolve(self, ticker: str) -> tuple[str, str]:
        """Return (company_name, sector). Returns ("", "unknown") on any failure."""
        try:
            import yfinance as yf

            info = yf.Ticker(ticker).info
            return info.get("longName", ""), info.get("sector", "unknown")
        except Exception as exc:
            logger.debug("[yfinance_resolver] {} failed to resolve: {}", ticker, exc)
            return "", "unknown"
