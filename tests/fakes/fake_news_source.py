"""Fake NewsHeadlinePort for tests."""

from __future__ import annotations

from datetime import datetime


class FakeNewsSource:
    """In-memory NewsHeadlinePort for tests. Applies point-in-time filtering."""

    def __init__(self, headlines: list[tuple[str, str]]) -> None:
        self._headlines = headlines

    def get_recent_headlines(
        self, ticker: str, since: datetime, until: datetime | None = None
    ) -> list[tuple[str, str]]:
        out: list[tuple[str, str]] = []
        for title, date in self._headlines:
            d = datetime.strptime(date, "%Y-%m-%d")
            if d >= since and (until is None or d <= until):
                out.append((title, date))
        return out
