"""Raw data caching mixin for reproducibility (ADR-017).
Append-only cache keyed by fetch timestamp.
"""
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


class CachingMixin:
    """Base class providing raw data caching.
    Cache layout: {cache_dir}/{symbol}/{YYYY-MM-DDTHH-MM-SS}.json
    Append-only: never overwrites past fetches. Load returns most recent.
    """

    def __init__(self, cache_dir: Path) -> None:
        self._cache_dir = cache_dir
        self._cache_dir.mkdir(parents=True, exist_ok=True)

    def save_to_cache(self, symbol: str, data: dict[str, Any]) -> Path:
        symbol_dir = self._cache_dir / symbol
        symbol_dir.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H-%M-%S")
        cache_path = symbol_dir / f"{timestamp}.json"
        counter = 0
        while cache_path.exists():
            counter += 1
            cache_path = symbol_dir / f"{timestamp}_{counter}.json"
        with open(cache_path, "w") as f:
            json.dump(data, f, default=str)
        return cache_path

    def load_from_cache(self, symbol: str) -> dict[str, Any] | None:
        symbol_dir = self._cache_dir / symbol
        if not symbol_dir.exists():
            return None
        cache_files = sorted(symbol_dir.glob("*.json"))
        if not cache_files:
            return None
        with open(cache_files[-1]) as f:
            data: dict[str, Any] = json.load(f)
        return data

    def has_cache(self, symbol: str) -> bool:
        symbol_dir = self._cache_dir / symbol
        if not symbol_dir.exists():
            return False
        return bool(list(symbol_dir.glob("*.json")))
