"""Task 12 — positions.render() TDD bootstrap tests."""

import adapters.visualization.tabs.positions as positions


def test_render_is_callable():
    assert callable(positions.render)


def test_threshold_constant():
    # small-book flat-treemap threshold is defined and sane
    assert positions.SMALL_BOOK_MAX == 5


def test_resolve_book_prefers_session_upload(monkeypatch):
    """An in-session uploaded book wins over CSV and SQLite, aggregated by ticker."""
    from application.holdings_reader import Holding

    monkeypatch.setattr(
        positions.st,
        "session_state",
        {"book": [Holding("AC.TO", 30.0, 600.0, "FHSA")]},
        raising=False,
    )
    holdings, source = positions._resolve_book("unused.db")
    assert source == "uploaded book"
    assert {h.symbol for h in holdings} == {"AC.TO"}


def test_resolve_book_falls_back_to_csv(monkeypatch, tmp_path):
    """No session book → read the canonical holdings.csv."""
    csv = tmp_path / "holdings.csv"
    csv.write_text(
        "Symbol,Quantity,Book Value (CAD),Exchange,Account Type\n"
        "RY,10,1000,TSX,TFSA\n"
    )
    monkeypatch.setattr(positions.st, "session_state", {}, raising=False)
    monkeypatch.setattr(positions, "HOLDINGS_CSV", str(csv))
    holdings, source = positions._resolve_book("unused.db")
    assert source == "holdings.csv"
    assert {h.symbol for h in holdings} == {"RY.TO"}


def test_resolve_book_falls_back_to_sqlite(monkeypatch, tmp_path):
    """No session book and no CSV → SQLite store (recorded trades / demo)."""
    from domain.models import Holding as DomainHolding

    sentinel = [DomainHolding("NVDA", 10.0, 100.0, "2026-01-01")]
    monkeypatch.setattr(positions.st, "session_state", {}, raising=False)
    monkeypatch.setattr(positions, "HOLDINGS_CSV", str(tmp_path / "missing.csv"))
    monkeypatch.setattr(
        "adapters.visualization.data_loader.load_holdings",
        lambda db_path: sentinel,
    )
    holdings, source = positions._resolve_book("unused.db")
    assert source == "recorded trades"
    assert holdings is sentinel
