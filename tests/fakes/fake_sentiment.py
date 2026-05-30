"""Fake SentimentPort for testing."""

from __future__ import annotations

from datetime import datetime

from domain.models import Sentiment


class FakeSentimentScorer:
    def __init__(
        self, scores: dict[str, float] | None = None, default_score: float = 0.5
    ):
        self._scores = scores or {}
        self._default = default_score
        self.score_calls: list[tuple[str, str]] = []

    def score_text(
        self, ticker: str, text: str, timestamp: datetime, source: str = "fake"
    ) -> list[Sentiment]:
        self.score_calls.append((ticker, text))
        score = self._scores.get(ticker, self._default)
        return [
            Sentiment(
                source=source,
                timestamp=timestamp,
                sentiment_score=score,
                confidence=0.8,
                text_snippet=text[:200] if text else None,
            )
        ]

    def get_sentiment(
        self,
        symbol: str,
        prediction_time: datetime,
        start_date: datetime | None = None,
        end_date: datetime | None = None,
    ) -> list[Sentiment]:
        return [
            Sentiment(
                source="fake",
                timestamp=prediction_time,
                sentiment_score=self._scores.get(symbol, self._default),
                confidence=0.8,
            )
        ]
