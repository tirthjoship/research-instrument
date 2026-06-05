from __future__ import annotations

from datetime import datetime

from domain.universe import UniverseEntry


class FakeUniverseProvider:
    def __init__(self, entries: list[UniverseEntry] | None = None) -> None:
        self._entries = entries or []
        self.calls: list[datetime] = []

    def get_universe(self, now: datetime) -> list[UniverseEntry]:
        self.calls.append(now)
        return self._entries
