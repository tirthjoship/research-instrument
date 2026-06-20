"""Self-updating free-model discovery. Polls wired providers' list endpoints,
ranks by version recency, drops deprecated. Availability not quality (spec §7b)."""

from __future__ import annotations

import json
import re
from datetime import datetime, timedelta
from typing import Callable


def _version_key(name: str) -> tuple[int, ...]:
    nums = [int(n) for n in re.findall(r"\d+", name)]
    return tuple(nums) if nums else (0,)


def gemini_lister() -> list[str]:
    """List available Gemini flash models (free family). Lazy import — no key at module load."""
    try:
        import google.generativeai as genai

        models = genai.list_models()
        result: list[str] = []
        for m in models:
            name: str = m.name if isinstance(m.name, str) else str(m.name)
            # Strip leading "models/" prefix
            if name.startswith("models/"):
                name = name[len("models/") :]
            if "flash" in name:
                result.append(name)
        return result
    except Exception:
        return []


class ModelRegistry:
    def __init__(
        self,
        listers: dict[str, Callable[[], list[str]]],
        deprecated: set[str] | None = None,
    ) -> None:
        self._listers = listers
        self._deprecated = deprecated or set()

    def preferred(self, provider: str) -> list[str]:
        try:
            models = self._listers[provider]()
        except Exception:
            return []
        live = [m for m in models if m not in self._deprecated]
        return sorted(live, key=_version_key, reverse=True)

    def cached_preferred(
        self,
        provider: str,
        *,
        now: datetime,
        read_text: Callable[[str], str],
        write_text: Callable[[str, str], None],
        ttl_days: int = 7,
        cache_path: str = "data/cache/model_registry.json",
    ) -> list[str]:
        """Return preferred model list, using a TTL-bounded JSON cache.

        ``now``, ``read_text``, and ``write_text`` are injected so tests
        can supply a fake clock and in-memory storage — no real time or disk.
        """
        # Attempt to read from cache
        try:
            raw = read_text(cache_path)
            data: dict[str, object] = json.loads(raw)
            cached_at_str = data.get("cached_at")
            if isinstance(cached_at_str, str):
                cached_at = datetime.fromisoformat(cached_at_str)
                if now - cached_at < timedelta(days=ttl_days):
                    cached_list = data.get(provider)
                    if isinstance(cached_list, list):
                        return [str(m) for m in cached_list]
        except Exception:
            pass  # missing or corrupt cache → recompute

        # Recompute
        fresh = self.preferred(provider)

        # Merge into existing cache data (preserve other providers)
        try:
            raw = read_text(cache_path)
            existing: dict[str, object] = json.loads(raw)
        except Exception:
            existing = {}

        existing[provider] = fresh
        existing["cached_at"] = now.isoformat()
        write_text(cache_path, json.dumps(existing))
        return fresh
