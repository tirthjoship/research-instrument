# tests/test_sa_market_signals_compose.py
from types import SimpleNamespace

from adapters.visualization.tabs.stock_analysis import compose


def _result():
    return SimpleNamespace(
        company_name="NVIDIA Corp",
        ticker="NVDA",
        sector="Semiconductors",
        current_price=172.0,
        change_pct=1.28,
        market_cap=4.2e12,
        info={
            "exchange": "NASDAQ",
            "fiftyTwoWeekLow": 86.6,
            "fiftyTwoWeekHigh": 189.5,
            "52WeekChange": 0.42,
            "SandP52WeekChange": 0.14,
            "beta": 1.7,
            "twoHundredDayAverage": 130.0,
            "fiftyDayAverage": 160.0,
            "heldPercentInstitutions": 0.66,
            "heldPercentInsiders": 0.04,
            "trailingPE": 52.0,
            "freeCashflow": 72e9,
            "marketCap": 4.2e12,
            "revenueGrowth": 0.69,
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
            "pegRatio": 0.75,
            "forwardPE": 34.0,
            "priceToSalesTrailingTwelveMonths": 28.0,
            "enterpriseToEbitda": 45.0,
        },
        peer_percentiles={"P/E": 78.0},
        peer_data=[{"ticker": "NVDA", "pe": 52.0}],
        analyst_panel=SimpleNamespace(
            count=42,
            mean_rating=1.6,
            target_mean=200.0,
            target_high=260.0,
            target_low=150.0,
            as_of="2026-06-27",
            data_gap=False,
        ),
        insider_transactions=[{"value": -48_000_000}],
        buzz_signals=[
            SimpleNamespace(
                source="reddit",
                mention_count=30,
                sentiment_raw=0.3,
                fetched_at="2026-06-27",
            )
        ],
        supply_chain_group={
            "group": "AI semis",
            "leaders": ["NVDA"],
            "followers": ["AMD"],
            "typical_lag_days": 3,
            "notes": "n",
            "_is_leader": True,
        },
        quarterly_financials=None,
        quarterly_balance_sheet=None,
    )


def test_market_inner_two_panels():
    html = compose.build_market_inner(_result())
    assert (
        "Performance" in html
        and "Ownership" in html
        and html.count('class="sa-pnl"') == 2
    )


def test_signals_inner_four_panels_and_banner():
    html = compose.build_signals_inner(_result())
    for name in ("Analyst", "Buzz", "Sentiment", "Supply"):
        assert name in html
    assert html.count('class="sa-pnl"') == 4
    assert "falsified" in html.lower()  # D12 banner


def test_top_html_groups_populated():
    html = compose.build_top_html(_result(), None)
    im = html.index('id="sa-market"')
    isig = html.index('id="sa-signals"')
    assert "Performance" in html[im:isig]
    assert "Sentiment" in html[isig:]
