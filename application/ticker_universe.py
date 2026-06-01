"""Ticker universe loader — config-driven, deduplicating, sorted."""

from __future__ import annotations

from pathlib import Path


def load_ticker_universe(ticker_files: list[Path]) -> list[str]:
    """Load tickers from text files, deduplicate, sort alphabetically.

    Each file: one ticker per line. Lines starting with # are comments.
    Empty lines and whitespace-only lines are skipped.
    """
    tickers: set[str] = set()
    for filepath in ticker_files:
        for line in filepath.read_text().splitlines():
            stripped = line.strip()
            if not stripped or stripped.startswith("#"):
                continue
            tickers.add(stripped)
    return sorted(tickers)
