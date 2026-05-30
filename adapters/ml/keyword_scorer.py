"""Rule-based keyword sentiment scorer.

Counts bullish/bearish keyword hits in text, normalizes to [-1, 1].
Fast baseline — runs in <1ms per article. Parallel with Flan-T5 (ADR-008).
"""

from __future__ import annotations

from datetime import datetime

from domain.models import Sentiment

BULLISH_KEYWORDS: list[str] = [
    "beat",
    "beats",
    "exceeded",
    "record",
    "surge",
    "surges",
    "rally",
    "growth",
    "upgrade",
    "upgrades",
    "outperform",
    "strong",
    "profit",
    "gains",
    "positive",
    "optimistic",
    "bullish",
    "breakout",
    "soar",
    "boom",
    "revenue growth",
    "earnings beat",
    "buy rating",
    "price target raised",
    "all-time high",
    "momentum",
    "recovery",
    "upside",
    "dividend increase",
]

BEARISH_KEYWORDS: list[str] = [
    "miss",
    "misses",
    "missed",
    "decline",
    "declines",
    "drop",
    "drops",
    "loss",
    "losses",
    "recall",
    "recalls",
    "lawsuit",
    "layoff",
    "layoffs",
    "downgrade",
    "downgrades",
    "underperform",
    "weak",
    "negative",
    "bearish",
    "crash",
    "plunge",
    "sell-off",
    "selloff",
    "warning",
    "risk",
    "debt",
    "default",
    "bankruptcy",
    "investigation",
    "fine",
    "penalty",
    "revenue decline",
    "earnings miss",
    "sell rating",
    "price target cut",
]


class KeywordScorer:
    """Rule-based sentiment scorer using keyword matching."""

    def __init__(
        self,
        bullish: list[str] | None = None,
        bearish: list[str] | None = None,
    ) -> None:
        self._bullish = [k.lower() for k in (bullish or BULLISH_KEYWORDS)]
        self._bearish = [k.lower() for k in (bearish or BEARISH_KEYWORDS)]

    def score_text(
        self,
        ticker: str,
        text: str,
        timestamp: datetime,
        source: str = "unknown",
    ) -> list[Sentiment]:
        """Score a single text snippet and return a one-element Sentiment list."""
        text_lower = text.lower()
        bull_hits = sum(1 for kw in self._bullish if kw in text_lower)
        bear_hits = sum(1 for kw in self._bearish if kw in text_lower)
        total_hits = bull_hits + bear_hits

        if total_hits == 0:
            score = 0.0
            confidence = 0.1
        else:
            raw = (bull_hits - bear_hits) / total_hits
            score = max(-1.0, min(1.0, raw))
            confidence = min(1.0, total_hits / 10.0)

        return [
            Sentiment(
                source=source,
                timestamp=timestamp,
                sentiment_score=score,
                confidence=confidence,
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
        """SentimentPort interface — returns empty (use score_text directly)."""
        return []
