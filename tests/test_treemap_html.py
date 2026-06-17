"""Tests for build_treemap_html — squarified treemap HTML builder."""

from adapters.visualization.components.treemap import build_treemap_html
from adapters.visualization.portfolio_view import PortfolioRow


def _row(tk: str, sec: str, w: float, pnl: float, today: float, v: str) -> PortfolioRow:
    return PortfolioRow(tk, sec, w, 100, 100, pnl, today, v, "", None, 1.0, 1)


def _rows() -> list[PortfolioRow]:
    return [
        _row("NVDA", "Tech", 40.0, 75.0, 2.0, "HOLD"),
        _row("AAPL", "Tech", 25.0, -3.0, -0.5, "TRIM"),
        _row("XOM", "Energy", 20.0, 6.0, 1.0, "HOLD"),
        _row("ZZZ", "Unknown", 15.0, -2.0, -0.3, "HOLD"),
    ]


def test_grouped_renders_sectors_and_anchors() -> None:
    html = build_treemap_html(_rows(), lens="pnl", width=960.0, height=360.0)
    assert "Technology" in html or "Tech" in html
    assert 'href="?inspect=NVDA"' in html
    assert "Unknown" in html  # unknown sector block present


def test_small_book_is_flat() -> None:
    html = build_treemap_html(
        _rows()[:3], lens="pnl", width=960.0, height=360.0, flat=True
    )
    # flat mode: no sector header text, tiles still present
    assert 'href="?inspect=NVDA"' in html


def test_hover_tip_has_exact_numbers() -> None:
    html = build_treemap_html(_rows(), lens="pnl", width=960.0, height=360.0)
    assert "40.0%" in html  # weight
    assert "+75.0%" in html  # lifetime
    assert "+2.0%" in html  # today
