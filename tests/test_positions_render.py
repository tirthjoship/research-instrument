"""Task 12 — positions.render() TDD bootstrap tests."""

import adapters.visualization.tabs.positions as positions
from domain.outcome import TradeOutcome


def test_render_is_callable():
    assert callable(positions.render)


def test_threshold_constant():
    # small-book flat-treemap threshold is defined and sane
    assert positions.SMALL_BOOK_MAX == 5


def test_resolve_book_prefers_session_upload(monkeypatch):
    """An in-session uploaded book (flagged non-sample) wins over the bundled
    sample book, aggregated by ticker."""
    from application.holdings_reader import Holding

    monkeypatch.setattr(
        positions.st,
        "session_state",
        {
            "book": [Holding("AC.TO", 30.0, 600.0, "FHSA")],
            "is_sample_book": False,
        },
        raising=False,
    )
    holdings, source, _reports_dir = positions._resolve_book()
    assert source == "uploaded book"
    assert {h.symbol for h in holdings} == {"AC.TO"}


def test_resolve_book_falls_back_to_sample_when_session_empty(monkeypatch):
    """No session upload (cold start) → the bundled sample book, never
    data/personal/holdings.csv or SQLite."""
    monkeypatch.setattr(positions.st, "session_state", {}, raising=False)

    holdings, source, _reports_dir = positions._resolve_book()

    assert source == "sample book"
    assert {h.symbol for h in holdings} == {
        "AAPL",
        "MSFT",
        "NVDA",
        "GOOGL",
        "AMZN",
        "TSLA",
        "META",
        "JPM",
        "V",
        "BRK-B",
    }


def test_resolve_book_falls_back_to_sample_when_still_flagged_sample(monkeypatch):
    """Even if session_state["book"] holds a book, is_sample_book=True must
    still route to the bundled sample book — matches _handle_onboarding's own
    session seeding on cold start."""
    from application.holdings_reader import Holding

    monkeypatch.setattr(
        positions.st,
        "session_state",
        {
            "book": [Holding("AAPL", 10.0, 1800.0, "TFSA")],
            "is_sample_book": True,
        },
        raising=False,
    )

    holdings, source, _reports_dir = positions._resolve_book()

    assert source == "sample book"
    assert len(holdings) == 10


def test_canadian_holding_shows_cad_symbol(monkeypatch):
    """A TSX-suffixed ticker's dollar values in the closed-positions table
    must show C$, not bare $ — showing bare $ would misrepresent CAD
    amounts as USD."""
    outcome = TradeOutcome(
        ticker="RY.TO",
        buy_trade_id="b1",
        sell_trade_id="s1",
        buy_price=120.0,
        sell_price=130.0,
        quantity=10,
        buy_date="2026-01-01",
        sell_date="2026-01-10",
        holding_days=9,
        return_pct=8.3,
        return_dollar=100.0,
        signals_at_entry=[],
        conviction_at_entry=0.5,
    )

    captured: list[str] = []
    monkeypatch.setattr(positions.st, "write", lambda html, **kw: captured.append(html))

    positions._render_closed_positions_table([outcome])

    import re

    assert len(captured) == 1
    html = captured[0]
    assert "C$120.00" in html
    assert "C$130.00" in html
    assert "+C$100.00" in html
    # No bare (non-CAD-prefixed) "$" immediately before a number — that would
    # misrepresent a CAD amount as USD.
    assert re.search(r"(?<!C)\$\d", html) is None
