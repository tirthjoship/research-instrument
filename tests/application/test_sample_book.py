from __future__ import annotations

from application.sample_book import load_sample_book


def test_sample_book_has_ten_holdings() -> None:
    book = load_sample_book()
    assert len(book) == 10
    tickers = {h.ticker for h in book}
    assert "AAPL" in tickers and "MSFT" in tickers
