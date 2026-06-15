"""GICS sector lookup with a JSON cache. Offline-safe: unknown → "Unknown" (DATA-GAP)."""

from __future__ import annotations

import json
from collections.abc import Callable
from pathlib import Path


def _yf_fetch(ticker: str) -> str | None:
    try:
        import yfinance as yf  # lazy import for CI safety

        return yf.Ticker(ticker).info.get("sector")  # type: ignore[no-any-return]
    except Exception:
        return None


class SectorProvider:
    def __init__(
        self,
        cache_path: str = "data/personal/sector_map.json",
        fetcher: Callable[[str], str | None] = _yf_fetch,
    ) -> None:
        self._path = Path(cache_path)
        self._fetch = fetcher
        self._cache: dict[str, str] = {}
        if self._path.exists():
            try:
                loaded = json.loads(self._path.read_text())
                if isinstance(loaded, dict):
                    self._cache = {str(k): str(v) for k, v in loaded.items()}
            except Exception:
                self._cache = {}

    def sector(self, ticker: str) -> str:
        if ticker in self._cache:
            return self._cache[ticker]
        got = self._fetch(ticker) or "Unknown"
        self._cache[ticker] = got
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._path.write_text(json.dumps(self._cache, indent=2))
        return got
