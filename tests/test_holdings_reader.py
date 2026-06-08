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
