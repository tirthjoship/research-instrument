"""Fake HistoricalSentimentPort for testing."""

from __future__ import annotations

from datetime import datetime

from domain.models import Sentiment


class FakeHistoricalSentiment:
    def __init__(self, sentiments: list[Sentiment] | None = None):
        self._sentiments = sentiments or []
        self.calls: list[tuple[str, datetime, datetime]] = []

    def get_historical_sentiment(
        self,
        symbol: str,
        start_date: datetime,
        end_date: datetime,
    ) -> list[Sentiment]:
        self.calls.append((symbol, start_date, end_date))
        return [s for s in self._sentiments if start_date <= s.timestamp <= end_date]
