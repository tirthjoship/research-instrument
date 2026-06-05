from __future__ import annotations

from datetime import datetime

from domain.models import AttentionPoint


class FakeAttentionSeries:
    def __init__(self, points: list[AttentionPoint] | None = None) -> None:
        self._points = points or []

    def get_attention_series(
        self, ticker: str, start: datetime, end: datetime
    ) -> list[AttentionPoint]:
        return [
            p
            for p in self._points
            if p.ticker == ticker and start <= p.timestamp <= end
        ]
