"""Backward-compatibility shim — SQLiteStore moved to adapters.data.store."""

from adapters.data.store import SQLiteStore

__all__ = ["SQLiteStore"]
