"""Tests for the daily-scan --prune-days wiring (unit-level, no CliRunner —
daily_scan() itself pulls in 4 live adapters (RSS/Trends/News/Reddit) that
existing tests don't mock either; this isolates just the pruning helper)."""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any

from application.cli.scan_commands import _prune_buzz_data, _run_marketaux_scan
from domain.models import BuzzSignal


class _SpyStore:
    def __init__(self) -> None:
        self.prune_calls: list[datetime] = []
        self.saved: list[BuzzSignal] = []

    def prune_buzz_signals(self, before: datetime) -> int:
        self.prune_calls.append(before)
        return 3

    def save_buzz_signal(self, signal: BuzzSignal) -> None:
        self.saved.append(signal)


class _FakeKeyword:
    def score_text(
        self, ticker: str, text: str, timestamp: datetime, source: str
    ) -> list[Any]:
        return []


class _FakeMarketauxAdapter:
    def __init__(self, signals: list[BuzzSignal]) -> None:
        self._signals = signals
        self.calls: list[tuple[Any, ...]] = []

    def scan_headline_sources(
        self,
        scan_time: datetime,
        tickers: list[str] | None = None,
        alias_map: dict[str, str] | None = None,
    ) -> list[BuzzSignal]:
        self.calls.append((scan_time, tickers, alias_map))
        return self._signals


def _make_signal(ticker: str) -> BuzzSignal:
    return BuzzSignal(
        ticker=ticker,
        source="marketaux",
        mention_count=1,
        sentiment_raw=0.0,
        scorer="marketaux_raw",
        fetched_at=datetime(2026, 7, 18),
        article_hash=f"hash_{ticker}",
        article_text=f"{ticker} news headline",
    )


def test_run_marketaux_scan_stores_signals_and_looks_up_aliases() -> None:
    store = _SpyStore()
    keyword = _FakeKeyword()
    signals = [_make_signal("RELIANCE.NS")]
    adapter = _FakeMarketauxAdapter(signals)
    deps: dict[str, Any] = {"market_data": None}  # no get_company_name -> no alias

    found, scored = _run_marketaux_scan(
        store,
        keyword,
        deps,
        ["RELIANCE.NS"],
        datetime(2026, 7, 18),
        adapter=adapter,
    )

    assert found == 1
    assert store.saved == signals
    assert adapter.calls[0][1] == ["RELIANCE.NS"]
    assert adapter.calls[0][2] == {}


def test_run_marketaux_scan_builds_alias_map_from_company_name() -> None:
    store = _SpyStore()
    keyword = _FakeKeyword()
    adapter = _FakeMarketauxAdapter([])

    class _MarketData:
        def get_company_name(self, ticker: str) -> str | None:
            return "Reliance Industries" if ticker == "RELIANCE.NS" else None

    deps: dict[str, Any] = {"market_data": _MarketData()}

    _run_marketaux_scan(
        store,
        keyword,
        deps,
        ["RELIANCE.NS", "UNKNOWN.NS"],
        datetime(2026, 7, 18),
        adapter=adapter,
    )

    assert adapter.calls[0][2] == {"RELIANCE.NS": "Reliance Industries"}


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
