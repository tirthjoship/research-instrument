# tests/test_model_registry.py
import json
from datetime import datetime

from adapters.ml.model_registry import ModelRegistry


def test_registry_prefers_newer_and_drops_unavailable() -> None:
    # injected lister simulates a provider's list-models endpoint
    available = ["gemini-2.5-flash", "gemini-3.0-flash", "gemini-2.0-flash"]
    reg = ModelRegistry(
        listers={"gemini": lambda: available}, deprecated={"gemini-2.0-flash"}
    )
    order = reg.preferred("gemini")
    assert order[0] == "gemini-3.0-flash"  # newest ranked first
    assert "gemini-2.0-flash" not in order  # deprecated dropped


# ---------------------------------------------------------------------------
# Helpers for TTL cache tests — fake clock + in-memory dict-backed I/O
# ---------------------------------------------------------------------------


class _FakeStore:
    """In-memory dict-backed read_text / write_text for cache tests."""

    def __init__(self) -> None:
        self._data: dict[str, str] = {}

    def read_text(self, path: str) -> str:
        if path not in self._data:
            raise FileNotFoundError(path)
        return self._data[path]

    def write_text(self, path: str, text: str) -> None:
        self._data[path] = text


def _make_reg(lister_calls: list[int]) -> ModelRegistry:
    """ModelRegistry that counts how many times its lister is invoked."""

    def lister() -> list[str]:
        lister_calls.append(1)
        return ["gemini-2.5-flash", "gemini-3.0-flash"]

    return ModelRegistry(listers={"gemini": lister})


def test_cached_preferred_returns_cached_within_ttl() -> None:
    """Fresh cache within TTL → returns cached value WITHOUT calling the lister."""
    calls: list[int] = []
    reg = _make_reg(calls)
    store = _FakeStore()

    t0 = datetime(2026, 6, 1, 12, 0, 0)
    # Pre-populate cache with a value that differs from what lister would return
    pre_cached = json.dumps(
        {"gemini": ["gemini-3.0-flash"], "cached_at": t0.isoformat()}
    )
    store.write_text("data/cache/model_registry.json", pre_cached)

    # Query 3 days later — still within default 7-day TTL
    t1 = datetime(2026, 6, 4, 12, 0, 0)
    result = reg.cached_preferred(
        "gemini",
        now=t1,
        read_text=store.read_text,
        write_text=store.write_text,
    )

    assert result == ["gemini-3.0-flash"]  # returns cached value
    assert calls == []  # lister NOT invoked


def test_cached_preferred_recomputes_when_stale() -> None:
    """Stale cache (older than ttl_days) → recomputes from lister and rewrites cache."""
    calls: list[int] = []
    reg = _make_reg(calls)
    store = _FakeStore()

    t0 = datetime(2026, 6, 1, 12, 0, 0)
    pre_cached = json.dumps(
        {"gemini": ["gemini-3.0-flash"], "cached_at": t0.isoformat()}
    )
    store.write_text("data/cache/model_registry.json", pre_cached)

    # Query 10 days later — past the 7-day TTL
    t1 = datetime(2026, 6, 11, 12, 0, 0)
    result = reg.cached_preferred(
        "gemini",
        now=t1,
        read_text=store.read_text,
        write_text=store.write_text,
    )

    assert "gemini-3.0-flash" in result  # fresh list returned
    assert len(calls) == 1  # lister WAS invoked once
    # Verify cache was rewritten with new timestamp
    new_cache = json.loads(store.read_text("data/cache/model_registry.json"))
    assert new_cache["cached_at"] == t1.isoformat()


def test_cached_preferred_recomputes_when_cache_missing() -> None:
    """Missing cache → recomputes from lister."""
    calls: list[int] = []
    reg = _make_reg(calls)
    store = _FakeStore()  # empty store — no cache file

    t0 = datetime(2026, 6, 1, 12, 0, 0)
    result = reg.cached_preferred(
        "gemini",
        now=t0,
        read_text=store.read_text,
        write_text=store.write_text,
    )

    assert "gemini-3.0-flash" in result
    assert len(calls) == 1  # lister invoked
    # Cache should now exist
    new_cache = json.loads(store.read_text("data/cache/model_registry.json"))
    assert "gemini" in new_cache
