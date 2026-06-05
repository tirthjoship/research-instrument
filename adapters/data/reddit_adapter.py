"""Reddit adapter (PRAW) — pluggable retail-buzz source.

No-op when credentials are absent (enabled=False) so the pipeline runs
keyless until REDDIT_CLIENT_ID/SECRET/USER_AGENT are configured.
"""

from __future__ import annotations

import hashlib
import time
from datetime import datetime

import praw
from loguru import logger

from domain.models import BuzzSignal


class RedditAdapter:
    def __init__(
        self,
        client_id: str | None = None,
        client_secret: str | None = None,
        user_agent: str | None = None,
        subreddit_map: dict[str, list[str]] | None = None,
        throttle_s: float = 0.5,
    ) -> None:
        self.enabled = bool(client_id and client_secret and user_agent)
        self._subreddit_map = subreddit_map or {}
        self._throttle_s = throttle_s
        self._reddit: praw.Reddit | None = None
        if self.enabled:
            try:
                self._reddit = praw.Reddit(
                    client_id=client_id,
                    client_secret=client_secret,
                    user_agent=user_agent,
                    check_for_async=False,
                )
            except Exception as exc:  # noqa: BLE001
                logger.warning("Reddit init failed, disabling: {}", exc)
                self.enabled = False
        else:
            logger.info("Reddit adapter: no creds, running as no-op")

    def scan_sources(
        self, scan_time: datetime, tickers: list[str] | None = None
    ) -> list[BuzzSignal]:
        if not self.enabled or not tickers:
            return []
        assert self._reddit is not None
        out: list[BuzzSignal] = []
        for ticker in tickers:
            subs = self._subreddit_map.get(ticker, ["stocks"])
            count = 0
            try:
                for sub in subs:
                    time.sleep(self._throttle_s)
                    results = self._reddit.subreddit(sub).search(
                        ticker, time_filter="week", limit=50
                    )
                    count += sum(1 for _ in results)
            except Exception as exc:  # noqa: BLE001
                logger.warning("Reddit scan failed for {}: {}", ticker, exc)
                continue
            if count == 0:
                continue
            out.append(
                BuzzSignal(
                    ticker=ticker,
                    source="reddit",
                    mention_count=count,
                    sentiment_raw=0.0,
                    scorer="reddit",
                    fetched_at=scan_time,
                    article_hash=hashlib.sha256(
                        f"reddit:{ticker}:{scan_time.date().isoformat()}".encode()
                    ).hexdigest(),
                )
            )
        return out
