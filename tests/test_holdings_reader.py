def test_read_holdings_maps_tsx_suffix_and_parses(tmp_path):
    from application.holdings_reader import read_holdings

    p = tmp_path / "h.csv"
    p.write_text(
        "Symbol,Quantity,Book Value (CAD),Market Value,Account Type,Exchange\n"
        "RY,10,1000,1200,TFSA,TSX\n"
        "AAPL,5,500,800,RRSP,NASDAQ\n"
        "BRK.B,2,600,700,Non-registered,NYSE\n"
        ",0,0,0,TFSA,?\n"
    )
    hs = read_holdings(str(p))
    by = {h.ticker: h for h in hs}
    assert "RY.TO" in by
    assert "AAPL" in by
    assert "BRK-B" in by
    assert len(hs) == 3
    assert by["RY.TO"].account_type == "TFSA"
    assert by["RY.TO"].cost_basis == 1000.0


def test_read_holdings_missing_file_returns_empty(tmp_path):
    from application.holdings_reader import read_holdings

    assert read_holdings(str(tmp_path / "nope.csv")) == []


def test_aggregate_to_book_sums_duplicate_tickers_across_accounts():
    """Same ticker in two accounts → one domain Holding, shares + cost summed,
    purchase_price = total_cost / total_shares (book-value weighted)."""
    from application.holdings_reader import Holding, aggregate_to_book

    csv_holdings = [
        Holding(ticker="AC.TO", shares=30.0, cost_basis=600.0, account_type="FHSA"),
        Holding(ticker="AC.TO", shares=70.0, cost_basis=1400.0, account_type="TFSA"),
        Holding(ticker="WMT", shares=10.0, cost_basis=1000.0, account_type="RRSP"),
    ]
    book = aggregate_to_book(csv_holdings)
    by = {h.symbol: h for h in book}
    assert set(by) == {"AC.TO", "WMT"}
    # 100 shares total, $2000 total cost → $20.00/share weighted
    assert by["AC.TO"].quantity == 100.0
    assert by["AC.TO"].purchase_price == 20.0
    assert by["WMT"].quantity == 10.0
    assert by["WMT"].purchase_price == 100.0


def test_aggregate_to_book_skips_non_positive_cost():
    """Rows that can't yield a positive purchase_price are dropped (domain Holding
    forbids purchase_price <= 0), not fabricated."""
    from application.holdings_reader import Holding, aggregate_to_book

    csv_holdings = [
        Holding(ticker="CASH.TO", shares=5.0, cost_basis=0.0, account_type="TFSA"),
        Holding(ticker="RY.TO", shares=10.0, cost_basis=500.0, account_type="TFSA"),
    ]
    book = aggregate_to_book(csv_holdings)
    symbols = {h.symbol for h in book}
    assert symbols == {"RY.TO"}


def test_aggregate_to_book_empty_returns_empty():
    from application.holdings_reader import aggregate_to_book

    assert aggregate_to_book([]) == []


def test_to_yf_maps_nse_exchange():
    from application.holdings_reader import _to_yf

    assert _to_yf("RELIANCE", "NSE") == "RELIANCE.NS"


def test_to_yf_maps_bse_exchange():
    from application.holdings_reader import _to_yf

    assert _to_yf("RELIANCE", "BSE") == "RELIANCE.BO"


def test_to_yf_unmapped_exchange_falls_through_unchanged():
    """An exchange string not in any known set (typo, or a market this repo
    doesn't support yet) should return the bare symbol, not silently guess
    a suffix — matches the existing US fallback behavior."""
    from application.holdings_reader import _to_yf

    assert _to_yf("FOO", "NYSE") == "FOO"
