# tests/test_sa_compose_top.py
from types import SimpleNamespace

from adapters.visualization.tabs.stock_analysis import compose


def _result():
    return SimpleNamespace(
        company_name="NVIDIA Corp",
        ticker="NVDA",
        sector="Semiconductors",
        current_price=172.40,
        change_pct=1.28,
        market_cap=4.21e12,
        info={
            "exchange": "NASDAQ",
            "fiftyTwoWeekLow": 86.60,
            "fiftyTwoWeekHigh": 189.50,
            "revenueGrowth": 0.69,
            "trailingPE": 52.0,
            "freeCashflow": 72e9,
            "52WeekChange": 0.42,
            "SandP52WeekChange": 0.14,
        },
        peer_percentiles={"P/E": 78.0},
        analyst_panel=SimpleNamespace(
            mean_rating=1.6, target_mean=200.0, data_gap=False
        ),
        insider_transactions=[{"value": -48_000_000}],
        buzz_signals=[SimpleNamespace(sentiment_raw=0.3)],
    )


def _fit():
    return SimpleNamespace(
        evidence_grade="B",
        summary="Strong on momentum and quality; rich on value.",
        fit_flags=(
            SimpleNamespace(severity="CAUTION", message="Concentration — semis tilt"),
        ),
    )


def test_top_html_assembles_locked_flow_in_order():
    html = compose.build_top_html(_result(), _fit(), as_of="Jun 27 2026")
    assert 'class="sa-stage"' in html
    # order: hero -> synthesis -> vitals -> snowflake/fit -> colour key -> groups
    i_hero = html.index("sa-hero")
    i_syn = html.index("Story this week")
    i_vit = html.index("sa-grid6")
    i_fit = html.index("sa-twocol-fit")
    i_key = html.index("sa-ckey")
    i_grp = html.index('id="sa-fundamentals"')
    assert i_hero < i_syn < i_vit < i_fit < i_key < i_grp


def test_top_html_has_three_empty_group_shells():
    html = compose.build_top_html(_result(), _fit())
    assert html.count('<details class="sa-group"') == 3
    assert (
        'id="sa-fundamentals"' in html
        and 'id="sa-market"' in html
        and 'id="sa-signals"' in html
    )


def test_top_html_degrades_without_fit():
    html = compose.build_top_html(_result(), None)
    assert 'class="sa-stage"' in html and "sa-hero" in html
