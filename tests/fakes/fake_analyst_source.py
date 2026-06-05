from datetime import datetime

from domain.analyst import AnalystRating


class FakeAnalystSource:
    """In-memory AnalystRatingsPort for tests, with point-in-time filtering."""

    def __init__(self, events: list[AnalystRating]) -> None:
        self._events = events

    def get_rating_events(
        self, ticker: str, since: datetime, until: datetime | None = None
    ) -> list[AnalystRating]:
        return [
            e
            for e in self._events
            if e.ticker == ticker
            and e.published_at >= since
            and (until is None or e.published_at <= until)
        ]
