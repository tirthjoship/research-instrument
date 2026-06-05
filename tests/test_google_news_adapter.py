from datetime import datetime, timezone
from unittest.mock import MagicMock, patch


def test_google_news_emits_one_signal_per_ticker():
    from adapters.data.google_news_adapter import GoogleNewsAdapter

    entry = {
        "title": "AST SpaceMobile wins contract",
        "published_parsed": (2026, 6, 1, 0, 0, 0, 0, 0, 0),
    }
    feed = MagicMock(entries=[entry, entry, entry])
    with patch("adapters.data.google_news_adapter.feedparser.parse", return_value=feed):
        sigs = GoogleNewsAdapter(alias_map={"ASTS": "AST SpaceMobile"}).scan_sources(
            datetime(2026, 6, 2, tzinfo=timezone.utc), tickers=["ASTS"]
        )
    assert len(sigs) == 1
    assert sigs[0].ticker == "ASTS"
    assert sigs[0].source == "google_news"
    assert sigs[0].mention_count == 3


def test_google_news_returns_empty_on_error():
    from adapters.data.google_news_adapter import GoogleNewsAdapter

    with patch(
        "adapters.data.google_news_adapter.feedparser.parse",
        side_effect=Exception("boom"),
    ):
        sigs = GoogleNewsAdapter().scan_sources(
            datetime(2026, 6, 2, tzinfo=timezone.utc), tickers=["ASTS"]
        )
    assert sigs == []


def test_google_news_no_tickers_returns_empty():
    from adapters.data.google_news_adapter import GoogleNewsAdapter

    assert (
        GoogleNewsAdapter().scan_sources(datetime(2026, 6, 2, tzinfo=timezone.utc))
        == []
    )
