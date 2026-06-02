"""Fake EventClassifierPort for testing."""

from __future__ import annotations

from domain.models import ClassifiedEvent


class FakeEventClassifier:
    """In-memory EventClassifierPort for testing."""

    def __init__(self) -> None:
        self._responses: dict[str, ClassifiedEvent] = {}

    def add_response(self, headline: str, event: ClassifiedEvent) -> None:
        self._responses[headline] = event

    def classify(self, headline: str, date: str) -> ClassifiedEvent | None:
        return self._responses.get(headline)

    def classify_batch(self, headlines: list[tuple[str, str]]) -> list[ClassifiedEvent]:
        results: list[ClassifiedEvent] = []
        for headline, date in headlines:
            result = self.classify(headline, date)
            if result is not None:
                results.append(result)
        return results
