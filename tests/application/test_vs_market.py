from __future__ import annotations

from application.vs_market import compute_vs_market_1y


def test_vs_market_outperforms() -> None:
    # book +20%, spy +10% → +10 pp
    r = compute_vs_market_1y(book_closes=[100.0, 120.0], spy_closes=[100.0, 110.0])
    assert r is not None and round(r, 1) == 10.0


def test_vs_market_underperforms() -> None:
    r = compute_vs_market_1y([100.0, 90.0], [100.0, 110.0])
    assert round(r, 1) == -20.0


def test_vs_market_insufficient_is_none() -> None:
    assert compute_vs_market_1y([100.0], [100.0, 110.0]) is None
    assert compute_vs_market_1y([], []) is None
