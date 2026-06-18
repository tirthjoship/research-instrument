from adapters.visualization.components.portfolio_table import (
    TableState,
    apply_table_state,
)
from adapters.visualization.portfolio_view import PortfolioRow


def _r(tk, w, pnl):
    return PortfolioRow(tk, "Tech", w, w * 10, 100, pnl, 0.0, "HOLD", "", None, 1.0, 1)


def _rows():
    return [_r("A", 30, 5), _r("B", 10, -4), _r("C", 20, 12)]


def test_default_sort_weight_desc():
    out = apply_table_state(_rows(), TableState())
    assert [r.ticker for r in out] == ["A", "C", "B"]


def test_filter_losers():
    out = apply_table_state(_rows(), TableState(filter="loss"))
    assert [r.ticker for r in out] == ["B"]


def test_search():
    out = apply_table_state(_rows(), TableState(query="c"))
    assert [r.ticker for r in out] == ["C"]


def test_sort_pnl_asc():
    out = apply_table_state(_rows(), TableState(sort="pnl", ascending=True))
    assert [r.ticker for r in out] == ["B", "A", "C"]
