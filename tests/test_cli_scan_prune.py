"""Tests for the daily-scan --prune-days wiring (unit-level, no CliRunner —
daily_scan() itself pulls in 4 live adapters (RSS/Trends/News/Reddit) that
existing tests don't mock either; this isolates just the pruning helper)."""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any

from application.cli.scan_commands import _prune_buzz_data


class _SpyStore:
    def __init__(self) -> None:
        self.prune_calls: list[datetime] = []

    def prune_buzz_signals(self, before: datetime) -> int:
        self.prune_calls.append(before)
        return 3


def test_prune_buzz_data_noop_when_prune_days_none() -> None:
    store = _SpyStore()
    _prune_buzz_data(store, None)
    assert store.prune_calls == []


def test_prune_buzz_data_calls_store_with_correct_cutoff() -> None:
    store = _SpyStore()
    now = datetime(2026, 7, 17, 22, 0)

    _prune_buzz_data(store, 35, now=now)

    assert store.prune_calls == [now - timedelta(days=35)]


def test_prune_buzz_data_echoes_deleted_count(capsys: Any) -> None:
    store = _SpyStore()
    now = datetime(2026, 7, 17, 22, 0)

    _prune_buzz_data(store, 35, now=now)

    captured = capsys.readouterr()
    assert "Pruned 3 buzz signal(s)" in captured.out
