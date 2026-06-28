"""Tests for Task 7: build_fundamentals_inner + Fundamentals group wired into build_top_html."""

from types import SimpleNamespace

from adapters.visualization.tabs.stock_analysis import compose


def _result() -> object:
    return SimpleNamespace(
        company_name="NVIDIA Corp",
        ticker="NVDA",
        sector="Semiconductors",
        current_price=172.4,
        change_pct=1.28,
        market_cap=4.2e12,
        info={
            "exchange": "NASDAQ",
            "fiftyTwoWeekLow": 86.6,
            "fiftyTwoWeekHigh": 189.5,
            "trailingPE": 52.0,
            "forwardPE": 34.0,
            "pegRatio": 0.75,
            "priceToSalesTrailingTwelveMonths": 28.0,
            "enterpriseToEbitda": 45.0,
            "marketCap": 4.2e12,
            "freeCashflow": 72e9,
            "revenueGrowth": 0.69,
            "earningsGrowth": 0.82,
            "grossMargins": 0.75,
            "operatingMargins": 0.62,
            "profitMargins": 0.55,
            "returnOnEquity": 1.15,
            "totalRevenue": 130e9,
            "ebit": 80e9,
            "debtToEquity": 12.0,
            "totalCash": 43e9,
            "totalDebt": 9e9,
            "ebitda": 90e9,
            "interestExpense": 1e9,
            "currentRatio": 4.1,
            "quickRatio": 3.5,
        },
        peer_percentiles={"P/E": 78.0},
        peer_data=[{"ticker": "NVDA", "pe": 52.0}, {"ticker": "AMD", "pe": 38.0}],
        analyst_panel=SimpleNamespace(
            mean_rating=1.6, target_mean=200.0, data_gap=False
        ),
        insider_transactions=[],
        buzz_signals=[],
        quarterly_financials=None,
        quarterly_balance_sheet=None,
    )


def test_fundamentals_inner_has_four_panels() -> None:
    html = compose.build_fundamentals_inner(_result())
    for name in ("Valuation", "Growth", "Profitability", "Health"):
        assert name in html
    # Brief said html.count("sa-pnl") == 4, but panel sub-classes (sa-pnl-head,
    # sa-pnl-eyebrow, etc.) also contain the "sa-pnl" substring — each panel has ~11.
    # Using the exact outer wrapper class="sa-pnl" gives exactly 1 per panel = 4 total.
    assert html.count('class="sa-pnl"') == 4


def test_top_html_fundamentals_group_is_populated() -> None:
    html = compose.build_top_html(_result(), None)
    # the fundamentals group now holds real panels, not just the empty shell
    i = html.index('id="sa-fundamentals"')
    after = html[i:]
    assert "Valuation" in after
    assert 'class="sa-pnl"' in after
