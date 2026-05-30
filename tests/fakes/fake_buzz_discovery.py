"""Fake BuzzDiscoveryPort for testing."""

from __future__ import annotations

from datetime import datetime

from domain.models import BuzzSignal


class FakeBuzzDiscovery:
    def __init__(self, signals: list[BuzzSignal] | None = None):
        self._signals = signals or []
        self.scan_calls: list[datetime] = []

    def scan_sources(self, scan_time: datetime) -> list[BuzzSignal]:
        self.scan_calls.append(scan_time)
        return self._signals

    def get_buzz_signals(
        self,
        ticker: str | None = None,
        source: str | None = None,
        start_date: datetime | None = None,
        end_date: datetime | None = None,
    ) -> list[BuzzSignal]:
        results = self._signals
        if ticker:
            results = [s for s in results if s.ticker == ticker]
        if source:
            results = [s for s in results if s.source == source]
        return results
