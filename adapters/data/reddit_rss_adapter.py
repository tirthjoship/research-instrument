"""Reddit buzz via public search RSS — no API key required.

Uses subreddit search feeds (e.g. r/stocks) keyed by ticker. Each post becomes
one BuzzSignal with ``source=reddit`` for the news/social split in Buzz panels.
"""

from __future__ import annotations

import hashlib
import time
from datetime import datetime
from typing import Any
from urllib.parse import quote

import requests
from loguru import logger

from adapters.data.feed_fetch import DEFAULT_FEED_HEADERS
from domain.models import BuzzSignal

_DEFAULT_SUBREDDITS: tuple[str, ...] = ("stocks", "StockMarket", "investing")
_SEARCH_RSS = (
    "https://www.reddit.com/r/{subreddit}/search.rss"
    "?q={query}&restrict_sr=1&sort=new"
)
_MAX_POSTS_PER_SUB = 15
_REDDIT_HEADERS = {
    **DEFAULT_FEED_HEADERS,
    "User-Agent": "Mozilla/5.0 (compatible; multimodal-buzz-harvest/1.0)",
}


class RedditRssAdapter:
    """Keyless Reddit mention discovery via public RSS search feeds."""

    def __init__(
        self,
        subreddits: tuple[str, ...] | None = None,
        throttle_s: float = 2.5,
        max_posts_per_sub: int = _MAX_POSTS_PER_SUB,
        retry_backoff_s: float = 8.0,
    ) -> None:
        self._subreddits = subreddits or _DEFAULT_SUBREDDITS
        self._throttle_s = throttle_s
        self._max_posts = max_posts_per_sub
        self._retry_backoff_s = retry_backoff_s

    def _throttle(self) -> None:
        time.sleep(self._throttle_s)

    def _make_hash(self, ticker: str, link: str, title: str) -> str:
        payload = f"reddit_rss:{ticker}:{link}:{title}"
        return hashlib.sha256(payload.encode()).hexdigest()[:16]

    def _fetch_subreddit_posts(self, subreddit: str, ticker: str) -> list[Any]:
        url = _SEARCH_RSS.format(subreddit=subreddit, query=quote(ticker))
        for attempt, wait in enumerate((0.0, self._retry_backoff_s)):
            if wait > 0:
                logger.warning(
                    "Reddit RSS backoff {:.0f}s for r/{} {}", wait, subreddit, ticker
                )
                time.sleep(wait)
            response = requests.get(url, headers=_REDDIT_HEADERS, timeout=20)
            if response.status_code == 429:
                if attempt == 0:
                    continue
                logger.warning("Reddit RSS 429 for r/{} ticker {}", subreddit, ticker)
                return []
            response.raise_for_status()
            import feedparser

            feed = feedparser.parse(response.content)
            return list(getattr(feed, "entries", []))[: self._max_posts]
        return []

    def scan_headline_sources(
        self, scan_time: datetime, tickers: list[str] | None = None
    ) -> list[BuzzSignal]:
        """One BuzzSignal per Reddit post title mentioning the ticker."""
        if not tickers:
            return []
        out: list[BuzzSignal] = []
        seen_hashes: set[str] = set()
        for ticker in tickers:
            for subreddit in self._subreddits:
                try:
                    self._throttle()
                    entries = self._fetch_subreddit_posts(subreddit, ticker)
                except Exception as exc:  # noqa: BLE001
                    logger.warning(
                        "Reddit RSS failed r/{} {}: {}", subreddit, ticker, exc
                    )
                    continue
                for entry in entries:
                    title = (getattr(entry, "title", "") or "").strip()
                    if not title:
                        continue
                    link = getattr(entry, "link", "") or ""
                    article_hash = self._make_hash(ticker, link, title)
                    if article_hash in seen_hashes:
                        continue
                    seen_hashes.add(article_hash)
                    out.append(
                        BuzzSignal(
                            ticker=ticker,
                            source="reddit",
                            mention_count=1,
                            sentiment_raw=0.0,
                            scorer="reddit_rss_raw",
                            fetched_at=scan_time,
                            article_hash=article_hash,
                            article_text=title[:2000],
                        )
                    )
        return out

    def scan_sources(
        self, scan_time: datetime, tickers: list[str] | None = None
    ) -> list[BuzzSignal]:
        """Aggregate one BuzzSignal per ticker (mention_count = post total)."""
        headlines = self.scan_headline_sources(scan_time, tickers=tickers)
        if not headlines:
            return []
        totals: dict[str, int] = {}
        for sig in headlines:
            totals[sig.ticker] = totals.get(sig.ticker, 0) + sig.mention_count
        return [
            BuzzSignal(
                ticker=ticker,
                source="reddit",
                mention_count=count,
                sentiment_raw=0.0,
                scorer="reddit",
                fetched_at=scan_time,
                article_hash=hashlib.sha256(
                    f"reddit_agg:{ticker}:{scan_time.date().isoformat()}".encode()
                ).hexdigest()[:16],
            )
            for ticker, count in sorted(totals.items())
        ]
