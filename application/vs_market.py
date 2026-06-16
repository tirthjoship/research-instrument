"""Realized book-vs-SPY trailing return. Backward-looking only — no leakage."""

from __future__ import annotations


def compute_vs_market_1y(
    book_closes: list[float], spy_closes: list[float]
) -> float | None:
    if len(book_closes) < 2 or len(spy_closes) < 2:
        return None
    book_ret = (book_closes[-1] - book_closes[0]) / book_closes[0] * 100.0
    spy_ret = (spy_closes[-1] - spy_closes[0]) / spy_closes[0] * 100.0
    return book_ret - spy_ret
