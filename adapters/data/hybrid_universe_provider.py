"""Hybrid universe: curated thematic spine + corroboration overlay + buzz discovery."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING

import yaml
from loguru import logger

from domain.ports import BuzzDiscoveryPort
from domain.universe import UniverseEntry

if TYPE_CHECKING:
    from adapters.data.corroboration_store import CorroborationStore


class HybridUniverseProvider:
    def __init__(
        self,
        themes_path: str,
        buzz_discovery: BuzzDiscoveryPort,
        max_discovery: int = 50,
        store: "CorroborationStore | None" = None,
    ) -> None:
        self._themes_path = themes_path
        self._buzz = buzz_discovery
        self._max_discovery = max_discovery
        self._store = store

    def _spine(self) -> dict[str, str]:
        data = yaml.safe_load(Path(self._themes_path).read_text())
        out: dict[str, str] = {}
        for theme, tickers in data.get("themes", {}).items():
            for t in tickers:
                out.setdefault(t, theme)
        return out

    def _corroboration_overlay(self, now: datetime) -> dict[str, str]:
        if self._store is None:
            return {}
        return {
            e.ticker: "corroboration" for e in self._store.active_discovered(now.date())
        }

    def get_universe(self, now: datetime) -> list[UniverseEntry]:
        spine = self._spine()
        entries = [UniverseEntry(ticker=t, theme=theme) for t, theme in spine.items()]
        seen = set(spine)

        # Second source: corroboration overlay
        for ticker, theme in self._corroboration_overlay(now).items():
            if ticker in seen:
                logger.debug(
                    "[universe] {} in corroboration overlay but already in spine, skipping",
                    ticker,
                )
                continue
            seen.add(ticker)
            entries.append(UniverseEntry(ticker=ticker, theme=theme))

        # Third source: buzz discovery
        try:
            signals = self._buzz.scan_sources(now)
        except Exception as exc:  # noqa: BLE001
            logger.warning("buzz discovery failed, spine+overlay universe: {}", exc)
            return entries

        added = 0
        for sig in signals:
            t = sig.ticker
            if t in seen or added >= self._max_discovery:
                continue
            seen.add(t)
            entries.append(UniverseEntry(ticker=t, theme="discovery"))
            added += 1
        return entries
