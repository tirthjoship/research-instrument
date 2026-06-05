"""Tests for AlphaVantage news adapter and FakeNewsSource."""

from __future__ import annotations

from datetime import datetime

from adapters.data.alphavantage_news_adapter import parse_news_feed
from tests.fakes.fake_news_source import FakeNewsSource

# ---------------------------------------------------------------------------
# Canned Alpha Vantage payload
# ---------------------------------------------------------------------------

PAYLOAD = {
    "feed": [
        {"title": "US takes stake in Intel", "time_published": "20260604T130000"},
        {"title": "Future leak headline", "time_published": "20260701T130000"},
    ]
}


# ---------------------------------------------------------------------------
# FakeNewsSource tests
# ---------------------------------------------------------------------------


class TestFakeNewsSource:
    def test_drops_future_dated_headline_when_until_precedes_it(self) -> None:
        """FakeNewsSource must not return headlines published after `until`."""
        headlines = [
            ("Old news", "2026-05-01"),
            ("Future news", "2026-07-01"),
        ]
        source = FakeNewsSource(headlines)
        since = datetime(2026, 1, 1)
        until = datetime(2026, 6, 30)
        result = source.get_recent_headlines("AAPL", since=since, until=until)
        assert result == [("Old news", "2026-05-01")]

    def test_returns_headlines_within_window(self) -> None:
        headlines = [
            ("Old", "2025-12-31"),
            ("In-window", "2026-03-15"),
        ]
        source = FakeNewsSource(headlines)
        result = source.get_recent_headlines(
            "MSFT", since=datetime(2026, 1, 1), until=datetime(2026, 6, 30)
        )
        assert result == [("In-window", "2026-03-15")]

    def test_no_until_returns_all_from_since(self) -> None:
        headlines = [("A", "2026-01-01"), ("B", "2030-12-31")]
        source = FakeNewsSource(headlines)
        result = source.get_recent_headlines("X", since=datetime(2026, 1, 1))
        assert len(result) == 2


# ---------------------------------------------------------------------------
# parse_news_feed tests (pure, no network)
# ---------------------------------------------------------------------------


class TestParseNewsFeed:
    def test_converts_av_time_format_and_drops_future(self) -> None:
        """Parser converts YYYYMMDDTHHMMSS → YYYY-MM-DD and drops items after until."""
        until = datetime(2026, 6, 30)
        since = datetime(2026, 1, 1)
        result = parse_news_feed(PAYLOAD, since=since, until=until)
        assert result == [("US takes stake in Intel", "2026-06-04")]

    def test_empty_feed_returns_empty_list(self) -> None:
        result = parse_news_feed({"feed": []}, since=datetime(2026, 1, 1), until=None)
        assert result == []

    def test_missing_feed_key_returns_empty_list(self) -> None:
        result = parse_news_feed({}, since=datetime(2026, 1, 1), until=None)
        assert result == []

    def test_no_until_returns_all_since(self) -> None:
        result = parse_news_feed(PAYLOAD, since=datetime(2026, 1, 1), until=None)
        assert len(result) == 2

    def test_malformed_entry_is_skipped(self) -> None:
        payload = {
            "feed": [
                {"title": "Good", "time_published": "20260604T130000"},
                {"title": "Bad", "time_published": "not-a-date"},
            ]
        }
        result = parse_news_feed(payload, since=datetime(2026, 1, 1), until=None)
        assert result == [("Good", "2026-06-04")]
