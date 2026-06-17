"""Tests for build_table_html in portfolio_table.py."""

from adapters.visualization.components.portfolio_table import (
    TableState,
    build_table_html,
)
from adapters.visualization.portfolio_view import PortfolioRow


def _r(tk, w, pnl, yld, beta):
    return PortfolioRow(
        tk, "Tech", w, w * 10, 100, pnl, 0.3, "HOLD", "", yld, beta, 1.0
    )


def test_lean_has_core_columns_and_anchor():
    html = build_table_html([_r("AAA", 9.4, 19.1, 0.7, 1.1)], TableState())
    assert 'href="?inspect=AAA"' in html
    assert "Weight" in html and "Value" in html and "Verdict" in html
    assert "Beta" not in html  # hidden by default


def test_more_columns_reveals_yield_beta_cost():
    html = build_table_html(
        [_r("AAA", 9.4, 19.1, 0.7, 1.1)], TableState(show_more=True)
    )
    assert "Beta" in html and "Yield" in html and "Cost" in html
    assert "0.70%" in html  # dividend yield


def test_missing_yield_is_dash():
    html = build_table_html(
        [_r("AAA", 9.4, 19.1, None, 1.1)], TableState(show_more=True)
    )
    assert "—" in html
