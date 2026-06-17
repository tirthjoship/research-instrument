from adapters.visualization.components.portfolio_detail import build_detail_header_html
from adapters.visualization.portfolio_view import PortfolioRow


def test_detail_header_has_ticker_verdict_perf():
    r = PortfolioRow(
        "NVDA", "Tech", 9.4, 29410, 16760, 75.6, 2.1, "HOLD", "", 0.03, 1.7, 40
    )
    html = build_detail_header_html(r)
    assert "NVDA" in html
    assert "HOLD" in html
    assert "+75.6%" in html  # lifetime
    assert "+2.1%" in html  # today
    assert "9.4% of book" in html


def test_unknown_sector_datagap_note():
    r = PortfolioRow(
        "ZZZ", "Unknown", 1.0, 100, 100, 0.0, 0.0, "HOLD", "", None, None, 1
    )
    html = build_detail_header_html(r)
    assert "Unknown" in html
