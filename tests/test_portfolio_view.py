# tests/test_portfolio_view.py
from adapters.visualization.portfolio_view import (
    PortfolioRow,
    enrich_holdings,
    split_flagged_healthy,
    top5_weight,
)
from domain.models import Holding


def _h(sym, qty, cost):
    return Holding(
        symbol=sym, quantity=qty, purchase_price=cost, purchase_date="2026-01-02"
    )


def test_enrich_computes_value_pnl_weight():
    holdings = [_h("AAA", 10, 100.0), _h("BBB", 5, 200.0)]
    prices = {
        "AAA": {"price": 110.0, "change_pct": 1.0},
        "BBB": {"price": 180.0, "change_pct": -2.0},
    }
    infos = {
        "AAA": {"sector": "Tech", "beta": 1.2, "dividendYield": 0.5},
        "BBB": {"sector": "Energy", "beta": 0.8, "dividendYield": 0.0},
    }
    brief = {
        "AAA": {"verdict": "HOLD", "why": "ok", "trend_state": "uptrend"},
        "BBB": {"verdict": "TRIM", "why": "weak", "trend_state": "broken"},
    }
    rows = enrich_holdings(holdings, prices, infos, brief)
    aaa = next(r for r in rows if r.ticker == "AAA")
    assert aaa.value == 1100.0
    assert aaa.cost == 1000.0
    assert round(aaa.pnl, 1) == 10.0
    assert aaa.today == 1.0
    assert aaa.sector == "Tech"
    assert aaa.verdict == "HOLD"
    # weights sum to ~100
    assert abs(sum(r.weight for r in rows) - 100.0) < 0.01


def test_missing_sector_is_unknown():
    rows = enrich_holdings(
        [_h("ZZZ", 1, 10.0)],
        {"ZZZ": {"price": 10.0, "change_pct": 0.0}},
        {"ZZZ": {}},
        {},
    )
    assert rows[0].sector == "Unknown"
    assert rows[0].verdict == ""  # DATA-GAP: not in brief


def test_zero_dividend_yield_is_none_gap():
    rows = enrich_holdings(
        [_h("ZZZ", 1, 10.0)],
        {"ZZZ": {"price": 10.0, "change_pct": 0.0}},
        {"ZZZ": {"dividendYield": 0.0}},
        {},
    )
    assert rows[0].dividend_yield is None  # DATA-GAP rendered as "—"


def test_top5_weight():
    rows = [
        PortfolioRow("T%d" % i, "Tech", float(w), 0, 0, 0, 0, "HOLD", "", None, 1.0, 0)
        for i, w in enumerate([30, 25, 20, 10, 8, 4, 3])
    ]
    assert abs(top5_weight(rows) - (30 + 25 + 20 + 10 + 8)) < 0.01


def test_split_flagged_healthy():
    rows = [
        PortfolioRow("A", "Tech", 10, 0, 0, 0, 0, "REDUCE", "", None, 1.0, 0),
        PortfolioRow("B", "Tech", 10, 0, 0, 0, 0, "HOLD", "", None, 1.0, 0),
        PortfolioRow("C", "Tech", 10, 0, 0, 0, 0, "REVIEW", "", None, 1.0, 0),
    ]
    flagged, healthy = split_flagged_healthy(rows)
    assert [r.ticker for r in flagged] == ["A", "C"]  # REDUCE before REVIEW
    assert [r.ticker for r in healthy] == ["B"]
