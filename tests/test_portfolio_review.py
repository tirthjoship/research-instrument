# tests/test_portfolio_review.py
from adapters.visualization.components.portfolio_review import (
    build_calm_html,
    build_review_card_html,
)
from adapters.visualization.portfolio_view import PortfolioRow


def _row(tk, v, pnl):
    return PortfolioRow(
        tk, "Tech", 5.0, 100, 100, pnl, -0.5, v, "trend broke", None, 1.1, 10
    )


def test_review_card_has_anchor_and_pill():
    html = build_review_card_html(_row("PLTR", "REDUCE", -18.4))
    assert 'href="?inspect=PLTR"' in html
    assert "REDUCE" in html
    assert "-18.4%" in html
    assert "trend broke" in html


def test_card_border_class_by_verdict():
    assert "reduce" in build_review_card_html(_row("A", "REDUCE", -5))
    assert "trim" in build_review_card_html(_row("B", "TRIM", -2))
    assert "review" in build_review_card_html(_row("C", "REVIEW", 1))


def test_calm_state():
    html = build_calm_html()
    assert "Nothing needs review" in html
