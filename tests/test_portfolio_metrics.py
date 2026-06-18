from adapters.visualization.components.portfolio_metrics import build_hero_html


def test_hero_shows_value_pnl_review_concentration():
    html = build_hero_html(
        book_value=312840.0,
        cost=281470.0,
        pnl=31370.0,
        pnl_pct=11.1,
        spy_pct=7.1,
        needs_review=5,
        total_positions=60,
        top5=38.0,
    )
    assert "$312,840" in html
    assert "+$31,370" in html
    assert "+11.1%" in html
    assert "vs SPY +7.1%" in html
    assert ">5<" in html  # needs review count
    assert "of 60 positions" in html
    assert "38%" in html  # concentration


def test_hero_hides_spy_badge_when_gap():
    html = build_hero_html(
        book_value=1000.0,
        cost=1000.0,
        pnl=0.0,
        pnl_pct=0.0,
        spy_pct=None,
        needs_review=0,
        total_positions=1,
        top5=100.0,
    )
    assert "vs SPY" not in html


def test_negative_pnl_red():
    html = build_hero_html(
        book_value=900.0,
        cost=1000.0,
        pnl=-100.0,
        pnl_pct=-10.0,
        spy_pct=2.0,
        needs_review=0,
        total_positions=1,
        top5=100.0,
    )
    assert "-$100" in html and "-10.0%" in html
