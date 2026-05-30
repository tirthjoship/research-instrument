"""Tests for RSSAdapter — RSS feed scanner for financial news buzz signals.

TDD: tests written before implementation. feedparser.parse is always mocked —
never hit real RSS feeds in tests.
"""

from __future__ import annotations

from datetime import datetime
from unittest.mock import MagicMock, patch

from adapters.data.rss_adapter import RSSAdapter

SCAN_TIME = datetime(2026, 5, 30, 9, 0, 0)


# ---------------------------------------------------------------------------
# _extract_tickers
# ---------------------------------------------------------------------------


def test_extract_tickers_from_text() -> None:
    adapter = RSSAdapter(feeds={"test": "https://example.com/rss"}, request_delay=0)
    result = adapter._extract_tickers("Apple (AAPL) and Tesla (TSLA)")
    assert "AAPL" in result
    assert "TSLA" in result


def test_extract_tickers_handles_no_match() -> None:
    adapter = RSSAdapter(feeds={"test": "https://example.com/rss"}, request_delay=0)
    result = adapter._extract_tickers("The weather is nice today")
    assert result == []


def test_extract_tickers_filters_blocklist() -> None:
    adapter = RSSAdapter(feeds={"test": "https://example.com/rss"}, request_delay=0)
    result = adapter._extract_tickers("CEO said FDA approved the drug")
    assert "CEO" not in result
    assert "FDA" not in result


# ---------------------------------------------------------------------------
# _hash_article
# ---------------------------------------------------------------------------


def test_article_hash_deterministic() -> None:
    adapter = RSSAdapter(feeds={"test": "https://example.com/rss"}, request_delay=0)
    h1 = adapter._hash_article("https://example.com/1", "Apple surges")
    h2 = adapter._hash_article("https://example.com/1", "Apple surges")
    assert h1 == h2


def test_article_hash_unique() -> None:
    adapter = RSSAdapter(feeds={"test": "https://example.com/rss"}, request_delay=0)
    h1 = adapter._hash_article("https://example.com/1", "Apple surges")
    h2 = adapter._hash_article("https://example.com/2", "Tesla drops")
    assert h1 != h2


def test_article_hash_length() -> None:
    adapter = RSSAdapter(feeds={"test": "https://example.com/rss"}, request_delay=0)
    h = adapter._hash_article("https://example.com/1", "Some title")
    assert len(h) == 16


# ---------------------------------------------------------------------------
# scan_sources
# ---------------------------------------------------------------------------


@patch("adapters.data.rss_adapter.feedparser.parse")
def test_scan_sources_with_mocked_feed(mock_parse: MagicMock) -> None:
    mock_parse.return_value = MagicMock(
        entries=[
            MagicMock(
                title="Apple AAPL surges on earnings",
                summary="Strong growth reported",
                published_parsed=(2026, 5, 29, 14, 0, 0, 0, 0, 0),
                link="https://example.com/1",
            )
        ]
    )
    adapter = RSSAdapter(feeds={"reuters": "https://example.com/rss"}, request_delay=0)
    signals = adapter.scan_sources(SCAN_TIME)
    assert len(signals) >= 1
    assert signals[0].ticker == "AAPL"
    assert signals[0].source == "reuters"


@patch("adapters.data.rss_adapter.feedparser.parse")
def test_scan_sources_empty_feed_returns_no_signals(mock_parse: MagicMock) -> None:
    mock_parse.return_value = MagicMock(entries=[])
    adapter = RSSAdapter(
        feeds={"marketwatch": "https://example.com/rss"}, request_delay=0
    )
    signals = adapter.scan_sources(SCAN_TIME)
    assert signals == []


@patch("adapters.data.rss_adapter.feedparser.parse")
def test_scan_sources_skips_entry_with_no_tickers(mock_parse: MagicMock) -> None:
    mock_parse.return_value = MagicMock(
        entries=[
            MagicMock(
                title="The weather is nice today",
                summary="Sunny skies",
                published_parsed=(2026, 5, 29, 14, 0, 0, 0, 0, 0),
                link="https://example.com/2",
            )
        ]
    )
    adapter = RSSAdapter(feeds={"cnbc": "https://example.com/rss"}, request_delay=0)
    signals = adapter.scan_sources(SCAN_TIME)
    assert signals == []


@patch("adapters.data.rss_adapter.feedparser.parse")
def test_scan_sources_sets_fetched_at(mock_parse: MagicMock) -> None:
    mock_parse.return_value = MagicMock(
        entries=[
            MagicMock(
                title="NVDA NVIDIA record quarter",
                summary="Revenue beat",
                published_parsed=(2026, 5, 29, 14, 0, 0, 0, 0, 0),
                link="https://example.com/3",
            )
        ]
    )
    adapter = RSSAdapter(
        feeds={"yahoo_finance": "https://example.com/rss"}, request_delay=0
    )
    signals = adapter.scan_sources(SCAN_TIME)
    assert len(signals) >= 1
    assert signals[0].fetched_at == SCAN_TIME


@patch("adapters.data.rss_adapter.feedparser.parse")
def test_scan_sources_article_hash_populated(mock_parse: MagicMock) -> None:
    mock_parse.return_value = MagicMock(
        entries=[
            MagicMock(
                title="MSFT Microsoft cloud growth",
                summary="Azure up 40%",
                published_parsed=(2026, 5, 29, 14, 0, 0, 0, 0, 0),
                link="https://example.com/4",
            )
        ]
    )
    adapter = RSSAdapter(
        feeds={"seeking_alpha": "https://example.com/rss"}, request_delay=0
    )
    signals = adapter.scan_sources(SCAN_TIME)
    assert len(signals) >= 1
    assert len(signals[0].article_hash) == 16


@patch("adapters.data.rss_adapter.feedparser.parse")
def test_scan_sources_uses_default_feeds_when_none_provided(
    mock_parse: MagicMock,
) -> None:
    mock_parse.return_value = MagicMock(entries=[])
    adapter = RSSAdapter(request_delay=0)
    # Should call feedparser 6 times (one per default feed)
    adapter.scan_sources(SCAN_TIME)
    assert mock_parse.call_count == 6


@patch("adapters.data.rss_adapter.feedparser.parse")
def test_scan_sources_sentiment_raw_in_bounds(mock_parse: MagicMock) -> None:
    mock_parse.return_value = MagicMock(
        entries=[
            MagicMock(
                title="GOOG Google beats earnings strong revenue growth",
                summary="Beat estimates",
                published_parsed=(2026, 5, 29, 14, 0, 0, 0, 0, 0),
                link="https://example.com/5",
            )
        ]
    )
    adapter = RSSAdapter(
        feeds={"investing_com": "https://example.com/rss"}, request_delay=0
    )
    signals = adapter.scan_sources(SCAN_TIME)
    for sig in signals:
        assert -1.0 <= sig.sentiment_raw <= 1.0
