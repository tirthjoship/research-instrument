"""Domain types for the attributed 'case' block. Stdlib only."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class CasePoint:
    text: str
    source_tag: str  # e.g. "reported", "valuation", "Reuters", "your rule"


@dataclass(frozen=True)
class CaseContext:
    ticker: str
    facts: tuple[str, ...]  # plain-English fact lines from the 5 RAG dimensions
    news: tuple[
        tuple[str, str], ...
    ]  # (source, title) pairs — the ONLY free-text source


@dataclass(frozen=True)
class CaseResult:
    in_favor: tuple[CasePoint, ...]
    to_watch: tuple[CasePoint, ...]
    data_gap: bool
