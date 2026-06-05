# domain/universe.py
"""Universe membership entry. Pure domain."""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class UniverseEntry:
    ticker: str
    theme: str | None  # spine theme name, or "discovery"
