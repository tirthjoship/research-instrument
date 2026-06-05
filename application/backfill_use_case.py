"""Backfill the divergence base window from honest historical archives.

GDELT -> event buzz (article timestamps); Google Trends + Wikipedia ->
intensity series. Per-ticker isolation: one failure logs and continues.
Append-only persistence makes re-runs idempotent.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any

from loguru import logger


class BackfillHistoryUseCase:
    def __init__(self, gdelt: Any, trends: Any, wiki: Any, store: Any) -> None:
        self._gdelt = gdelt
        self._trends = trends
        self._wiki = wiki
        self._store = store

    def execute(
        self, tickers: list[str], now: datetime, days: int = 90
    ) -> dict[str, int]:
        start = now - timedelta(days=days)
        errors = 0
        for ticker in tickers:
            try:
                for sig in self._gdelt.get_historical_buzz(ticker, start, now):
                    self._store.save_buzz_signal(sig)
            except Exception as exc:  # noqa: BLE001
                logger.warning("Backfill GDELT failed for {}: {}", ticker, exc)
                errors += 1
            for src in (self._trends, self._wiki):
                try:
                    pts = src.get_attention_series(ticker, start, now)
                    if pts:
                        self._store.save_attention_points(pts)
                except Exception as exc:  # noqa: BLE001
                    logger.warning("Backfill attention failed for {}: {}", ticker, exc)
                    errors += 1
        return {"tickers": len(tickers), "errors": errors}
