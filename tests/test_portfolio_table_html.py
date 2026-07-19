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


def test_lean_has_core_columns_and_ticker():
    html = build_table_html([_r("AAA", 9.4, 19.1, 0.7, 1.1)], TableState())
    assert "AAA" in html
    assert "Weight" in html and "Value" in html and "Verdict" in html
    assert "Beta" not in html  # hidden by default


def test_table_rows_are_display_only_no_navigation():
    """Regression: ticker cells used to be <a href="?inspect=..."> anchors —
    a real browser-navigation click on Streamlit Cloud wiped session state
    (see portfolio_detail.py module docstring). Rows must never link."""
    html = build_table_html([_r("AAA", 9.4, 19.1, 0.7, 1.1)], TableState())
    assert "<a " not in html
    assert "href=" not in html


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


def test_canadian_ticker_shows_cad_symbol_for_value_and_cost():
    """A TSX-suffixed ticker's Value/Cost cells must show C$, not a bare $."""
    html = build_table_html(
        [_r("RY.TO", 9.4, 19.1, 0.7, 1.1)], TableState(show_more=True)
    )
    assert "C$94" in html  # value = w * 10
    assert "C$100" in html  # cost, hardcoded 100 in _r
    assert "$94" not in html.replace("C$94", "")
