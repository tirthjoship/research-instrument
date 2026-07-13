"""Task 12 — positions.render() TDD bootstrap tests."""

import adapters.visualization.tabs.positions as positions


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
    holdings, source = positions._resolve_book()
    assert source == "uploaded book"
    assert {h.symbol for h in holdings} == {"AC.TO"}


def test_resolve_book_falls_back_to_sample_when_session_empty(monkeypatch):
    """No session upload (cold start) → the bundled sample book, never
    data/personal/holdings.csv or SQLite."""
    monkeypatch.setattr(positions.st, "session_state", {}, raising=False)

    holdings, source = positions._resolve_book()

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

    holdings, source = positions._resolve_book()

    assert source == "sample book"
    assert len(holdings) == 10
