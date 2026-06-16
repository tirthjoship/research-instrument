"""Load the bundled demo book (no user data needed)."""

from __future__ import annotations

from application.holdings_reader import Holding, read_holdings

_SAMPLE_PATH = "data/sample/sample_book.csv"


def load_sample_book(path: str = _SAMPLE_PATH) -> list[Holding]:
    return read_holdings(path)
