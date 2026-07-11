"""RSS feed adapter for financial news buzz signal discovery.

Scans 6 financial RSS publishers, extracts ticker mentions, and produces
BuzzSignal domain objects for downstream sentiment scoring.
"""

from __future__ import annotations

import hashlib
import re
import time
from datetime import datetime
from typing import Any

from loguru import logger

from adapters.data.feed_fetch import fetch_feed
from domain.models import BuzzSignal

# ---------------------------------------------------------------------------
# Default feeds
# ---------------------------------------------------------------------------

DEFAULT_FEEDS: dict[str, str] = {
    "reuters": "https://feeds.reuters.com/reuters/businessNews",
    "marketwatch": "https://feeds.marketwatch.com/marketwatch/topstories/",
    "cnbc": "https://www.cnbc.com/id/100003114/device/rss/rss.html",
    "yahoo_finance": "https://finance.yahoo.com/news/rssindex",
    "seeking_alpha": "https://seekingalpha.com/feed.xml",
    "investing_com": "https://www.investing.com/rss/news.rss",
}

# ---------------------------------------------------------------------------
# Ticker blocklist — common acronyms that match [A-Z]{1,5} but aren't tickers
# ---------------------------------------------------------------------------

_TICKER_BLOCKLIST: frozenset[str] = frozenset(
    {
        "CEO",
        "CFO",
        "COO",
        "CTO",
        "IPO",
        "ETF",
        "SEC",
        "FDA",
        "GDP",
        "FED",
        "NYSE",
        "AI",
        "IT",
        "US",
        "UK",
        "EU",
        "USD",
        "THE",
        "FOR",
        "AND",
        "ARE",
        "HAS",
        "NOT",
        "BUT",
        "INC",
        "LLC",
        "LTD",
        "PLC",
        "SA",
        "AG",
        "BY",
        "AT",
        "IN",
        "ON",
        "OR",
        "TO",
        "OF",
        "AN",
        "BE",
        "DO",
        "GO",
        "IF",
        "NO",
        "SO",
        "UP",
        "AM",
        "PM",
        "WE",
        "MY",
        "IS",
        "IT",
        "CNBC",
        "NYSE",
        "NASDAQ",
        "SPY",
        "ETF",
        "IPO",
        "M&A",
        "PE",
        "PR",
        "DC",
        "HQ",
        "CA",
        "NY",
        "TX",
        "FL",
        "IL",
        "PA",
        "OH",
        "GA",
        "EPS",
        "EV",
        "FCF",
        "P&L",
        "YOY",
        "QOQ",
        "TTM",
        "EBIT",
        "EBITDA",
        "NAV",
        "AUM",
        "ROI",
        "ROE",
        "ROA",
        "ESG",
        "SaaS",
        "IPO",
        "SPAC",
        "OTC",
        "FX",
        "VC",
        "PE",
        "LBO",
        "M",
        "B",
        "T",
        "Q",
        "H",
        "A",
        "I",
        "S",
        "N",
        "E",
        "C",
        "R",
        "L",
        "D",
        "W",
    }
)

# Minimal known S&P 500 / large-cap tickers used for validation.
# The adapter only emits BuzzSignals for tickers in this set.
# Keeping this set broad enough to avoid false negatives for well-known names.
_KNOWN_TICKERS: frozenset[str] = frozenset(
    {
        "AAPL",
        "MSFT",
        "GOOG",
        "GOOGL",
        "AMZN",
        "META",
        "TSLA",
        "NVDA",
        "JPM",
        "JNJ",
        "V",
        "UNH",
        "HD",
        "PG",
        "MA",
        "BAC",
        "ABBV",
        "PFE",
        "AVGO",
        "LLY",
        "XOM",
        "CVX",
        "MRK",
        "COST",
        "KO",
        "WMT",
        "NFLX",
        "DIS",
        "CSCO",
        "TMO",
        "ACN",
        "ABT",
        "MCD",
        "CRM",
        "ADBE",
        "NKE",
        "TXN",
        "NEE",
        "QCOM",
        "WFC",
        "LIN",
        "DHR",
        "RTX",
        "UPS",
        "HON",
        "LOW",
        "SPGI",
        "AMGN",
        "CAT",
        "GS",
        "INTU",
        "IBM",
        "MDLZ",
        "ISRG",
        "AXP",
        "BLK",
        "DE",
        "BKNG",
        "SYK",
        "GILD",
        "ADI",
        "REGN",
        "VRTX",
        "LRCX",
        "MU",
        "AMAT",
        "KLAC",
        "MCHP",
        "AMD",
        "INTC",
        "ORCL",
        "NOW",
        "ZTS",
        "CI",
        "CVS",
        "ELV",
        "HUM",
        "MCK",
        "AIG",
        "C",
        "USB",
        "PNC",
        "TFC",
        "COF",
        "MS",
        "BK",
        "STT",
        "AMP",
        "SCHW",
        "MMC",
        "AON",
        "CB",
        "ALL",
        "PRU",
        "MET",
        "AFL",
        "TRV",
        "HIG",
        "ETN",
        "PH",
        "EMR",
        "ITW",
        "GE",
        "MMM",
        "DOV",
        "ROK",
        "AME",
        "FDX",
        "CSX",
        "NSC",
        "UNP",
        "DAL",
        "AAL",
        "UAL",
        "LUV",
        "ALK",
        "BA",
        "LMT",
        "NOC",
        "GD",
        "HII",
        "L3H",
        "TDG",
        "SPR",
        "T",
        "VZ",
        "TMUS",
        "CMCSA",
        "CHTR",
        "NFLX",
        "PARA",
        "WBD",
        "OXY",
        "SLB",
        "HAL",
        "BKR",
        "PSX",
        "VLO",
        "MPC",
        "COP",
        "DVN",
        "WBA",
        "CAG",
        "GIS",
        "K",
        "SJM",
        "CPB",
        "HRL",
        "MKC",
        "CLX",
        "PM",
        "MO",
        "BTI",
        "LVS",
        "WYNN",
        "MGM",
        "CZR",
        "SPG",
        "AMT",
        "CCI",
        "PLD",
        "WELL",
        "EQR",
        "AVB",
        "O",
        "DLR",
        "SO",
        "D",
        "AEP",
        "EXC",
        "DUK",
        "SRE",
        "ED",
        "ES",
        "FE",
        "ECL",
        "DD",
        "DOW",
        "LYB",
        "PPG",
        "SHW",
        "APD",
        "NUE",
        "FCX",
        "VALE",
        "RIO",
        "AA",
        "X",
        "CLF",
    }
)


class RSSAdapter:
    """Scans financial RSS feeds and extracts BuzzSignals per ticker mention.

    Args:
        feeds: Mapping of source_name -> RSS URL. Defaults to DEFAULT_FEEDS.
        request_delay: Seconds to sleep between feed requests. Default 1.0.
    """

    def __init__(
        self,
        feeds: dict[str, str] | None = None,
        request_delay: float = 1.0,
    ) -> None:
        self._feeds: dict[str, str] = feeds if feeds is not None else DEFAULT_FEEDS
        self._request_delay = request_delay

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def scan_sources(self, scan_time: datetime) -> list[BuzzSignal]:
        """Iterate all configured feeds and return BuzzSignals.

        Args:
            scan_time: The logical "now" time to stamp on every BuzzSignal.

        Returns:
            List of BuzzSignal objects, one per (ticker, article) pair found.
        """
        signals: list[BuzzSignal] = []
        for source_name, url in self._feeds.items():
            logger.debug("Fetching RSS feed: {} ({})", source_name, url)
            try:
                feed = fetch_feed(url)
                if not feed.entries:
                    logger.warning(
                        "RSS feed {} returned 0 entries (bozo={})",
                        source_name,
                        getattr(feed, "bozo", False),
                    )
                for entry in feed.entries:
                    entry_signals = self._entry_to_signals(
                        source_name, entry, scan_time
                    )
                    signals.extend(entry_signals)
            except Exception as exc:  # noqa: BLE001
                logger.warning("Failed to parse feed {}: {}", source_name, exc)
            if self._request_delay > 0:
                time.sleep(self._request_delay)

        logger.info(
            "RSS scan complete: {} signals from {} feeds",
            len(signals),
            len(self._feeds),
        )
        return signals

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _entry_to_signals(
        self,
        source_name: str,
        entry: Any,
        scan_time: datetime,
    ) -> list[BuzzSignal]:
        """Convert a single feedparser entry to a list of BuzzSignals.

        One signal is created per distinct ticker detected in the entry.
        sentiment_raw is set to 0.0 (neutral placeholder) — the actual
        sentiment scorer (keyword or Flan-T5) runs in a downstream step.
        """
        title: str = getattr(entry, "title", "") or ""
        summary: str = getattr(entry, "summary", "") or ""
        link: str = getattr(entry, "link", "") or ""
        text = f"{title} {summary}"

        tickers = self._extract_tickers(text)
        if not tickers:
            return []

        article_hash = self._hash_article(link, title)

        return [
            BuzzSignal(
                ticker=ticker,
                source=source_name,
                mention_count=text.upper().count(ticker),
                sentiment_raw=0.0,  # scored later by keyword / Flan-T5
                scorer="rss_raw",
                fetched_at=scan_time,
                article_hash=article_hash,
                article_text=text[:2000],
            )
            for ticker in tickers
        ]

    def _extract_tickers(self, text: str) -> list[str]:
        """Extract valid ticker symbols from free text.

        Strategy:
        1. Find all uppercase word tokens matching [A-Z]{1,5}.
        2. Remove blocklist words (CEO, FDA, …).
        3. Keep only tokens present in _KNOWN_TICKERS.

        Returns:
            Deduplicated list of ticker strings, order-stable.
        """
        candidates = re.findall(r"\b[A-Z]{1,5}\b", text)
        seen: dict[str, None] = {}
        result: list[str] = []
        for token in candidates:
            if token in _TICKER_BLOCKLIST:
                continue
            if token not in _KNOWN_TICKERS:
                continue
            if token not in seen:
                seen[token] = None
                result.append(token)
        return result

    def _hash_article(self, url: str, title: str) -> str:
        """Return first 16 hex chars of SHA-256(url + title) for dedup.

        Args:
            url: Article URL.
            title: Article title.

        Returns:
            16-character hex string.
        """
        payload = f"{url}||{title}".encode("utf-8")
        return hashlib.sha256(payload).hexdigest()[:16]
