# adapters/data/hybrid_universe_provider.py
"""Hybrid universe: curated thematic spine + dynamic buzz-discovery overlay."""
from __future__ import annotations

from datetime import datetime
from pathlib import Path

import yaml
from loguru import logger

from domain.ports import BuzzDiscoveryPort
from domain.universe import UniverseEntry


class HybridUniverseProvider:
    def __init__(
        self,
        themes_path: str,
        buzz_discovery: BuzzDiscoveryPort,
        max_discovery: int = 50,
    ) -> None:
        self._themes_path = themes_path
        self._buzz = buzz_discovery
        self._max_discovery = max_discovery

    def _spine(self) -> dict[str, str]:
        data = yaml.safe_load(Path(self._themes_path).read_text())
        out: dict[str, str] = {}
        for theme, tickers in data.get("themes", {}).items():
            for t in tickers:
                out.setdefault(t, theme)
        return out

    def get_universe(self, now: datetime) -> list[UniverseEntry]:
        spine = self._spine()
        entries = [UniverseEntry(ticker=t, theme=theme) for t, theme in spine.items()]
        try:
            signals = self._buzz.scan_sources(now)
        except Exception as exc:  # noqa: BLE001 - degrade gracefully
            logger.warning("buzz discovery failed, spine-only universe: {}", exc)
            return entries
        seen = set(spine)
        added = 0
        for sig in signals:
            t = sig.ticker
            if t in seen or added >= self._max_discovery:
                continue
            seen.add(t)
            entries.append(UniverseEntry(ticker=t, theme="discovery"))
            added += 1
        return entries
