# tests/test_sa_full_render.py
"""Full-dossier render smoke test for the stock_analysis tab.

Guards against:
- re-duplication of panels (any future regression that re-adds flat renders)
- missing panels or top sections
- structural breakage in build_top_html
"""
from types import SimpleNamespace

import pytest

from adapters.visualization.tabs.stock_analysis import compose


@pytest.fixture
def rich_result():
    """Rich result fixture — mirrors the pattern in test_sa_market_signals_compose.py."""
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
            "priceToSalesTrailing12Months": 28.0,
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


def test_full_dossier_renders_each_panel_once(rich_result):
    """Each of the 10 panel names must appear at least once; no duplicated sa-pnl wrappers."""
    html = compose.build_top_html(rich_result, None)

    # All 10 panel names must appear
    for name in (
        "Valuation",
        "Growth",
        "Profitability",
        "Health",
        "Performance",
        "Ownership",
        "Analyst",
        "Buzz",
        "Sentiment",
        "Supply",
    ):
        assert name in html, f"Panel '{name}' missing from full dossier HTML"

    # Exactly 10 sa-pnl wrappers — guards against re-duplication
    count = html.count('class="sa-pnl"')
    assert count == 10, (
        f"Expected exactly 10 sa-pnl wrappers, got {count}. "
        "This indicates panel duplication or a missing panel."
    )


def test_full_dossier_top_sections_present(rich_result):
    """Hero, synthesis, vitals, snowflake/fit, and colour key must all be present."""
    html = compose.build_top_html(rich_result, None)

    assert 'id="sa-hero"' in html, "sa-hero anchor missing"
    assert "Story this week" in html, "synthesis 'Story this week' eyebrow missing"
    assert 'class="sa-grid6"' in html, "vitals sa-grid6 missing"
    assert 'class="sa-twocol-fit"' in html, "sa-twocol-fit layout wrapper missing"
    assert 'class="sa-ckey"' in html, "colour key sa-ckey missing"


def test_full_dossier_group_ids_present(rich_result):
    """The three group section anchors must appear in the HTML."""
    html = compose.build_top_html(rich_result, None)

    assert 'id="sa-fundamentals"' in html, "sa-fundamentals group anchor missing"
    assert 'id="sa-market"' in html, "sa-market group anchor missing"
    assert 'id="sa-signals"' in html, "sa-signals group anchor missing"
