"""Tests for RedditRssAdapter — mocked HTTP, never hits live Reddit."""

from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

from adapters.data.reddit_rss_adapter import RedditRssAdapter

SCAN = datetime(2026, 7, 8, 9, 0, tzinfo=timezone.utc)


def _entry(title: str, link: str = "https://reddit.com/x") -> MagicMock:
    return MagicMock(title=title, link=link)


@patch("adapters.data.reddit_rss_adapter.requests.get")
def test_scan_headline_sources_parses_posts(mock_get: MagicMock) -> None:
    mock_resp = MagicMock(status_code=200, content=b"<rss/>")
    mock_get.return_value = mock_resp
    feed = MagicMock(entries=[_entry("NVDA to the moon"), _entry("Thoughts on NVDA?")])
    with patch("feedparser.parse", return_value=feed):
        adapter = RedditRssAdapter(subreddits=("stocks",), throttle_s=0)
        sigs = adapter.scan_headline_sources(SCAN, tickers=["NVDA"])
    assert len(sigs) == 2
    assert all(s.source == "reddit" for s in sigs)
    assert all(s.scorer == "reddit_rss_raw" for s in sigs)
    assert sigs[0].article_text


@patch("adapters.data.reddit_rss_adapter.requests.get")
def test_scan_headline_sources_skips_429(mock_get: MagicMock) -> None:
    mock_get.return_value = MagicMock(status_code=429, content=b"")
    adapter = RedditRssAdapter(subreddits=("wallstreetbets",), throttle_s=0)
    assert adapter.scan_headline_sources(SCAN, tickers=["NVDA"]) == []


def test_scan_sources_empty_tickers() -> None:
    adapter = RedditRssAdapter(throttle_s=0)
    assert adapter.scan_sources(SCAN, tickers=[]) == []
