"""Fake SourceReliabilityPort for testing."""

from __future__ import annotations

from domain.models import SourceReliability


class FakeSourceReliability:
    def __init__(self) -> None:
        self._records: dict[tuple[str, str | None], dict[str, int]] = {}

    def record_outcome(
        self,
        source: str,
        ticker: str,
        predicted_direction: float,
        actual_direction: float,
    ) -> None:
        key = (source, ticker)
        if key not in self._records:
            self._records[key] = {"correct": 0, "total": 0}
        self._records[key]["total"] += 1
        if (predicted_direction >= 0) == (actual_direction >= 0):
            self._records[key]["correct"] += 1

    def get_reliability(
        self, source: str, ticker: str | None = None
    ) -> SourceReliability:
        key = (source, ticker)
        if key not in self._records:
            return SourceReliability(
                source=source, ticker=ticker, correct_calls=0, total_calls=0
            )
        r = self._records[key]
        return SourceReliability(
            source=source,
            ticker=ticker,
            correct_calls=r["correct"],
            total_calls=r["total"],
        )

    def get_all_reliabilities(self) -> list[SourceReliability]:
        return [
            SourceReliability(
                source=s, ticker=t, correct_calls=r["correct"], total_calls=r["total"]
            )
            for (s, t), r in self._records.items()
        ]
