"""Shared HTTP fetch for RSS / Atom feeds (browser-like User-Agent)."""

from __future__ import annotations

from typing import Any

import feedparser
import requests

# Many finance publishers block the default feedparser / python-requests UA.
DEFAULT_FEED_HEADERS: dict[str, str] = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept": "application/rss+xml, application/xml, text/xml, */*;q=0.8",
}


def fetch_feed(url: str, *, timeout: float = 15.0) -> Any:
    """GET *url* with a browser User-Agent and parse via feedparser."""
    response = requests.get(url, headers=DEFAULT_FEED_HEADERS, timeout=timeout)
    response.raise_for_status()
    return feedparser.parse(response.content)
