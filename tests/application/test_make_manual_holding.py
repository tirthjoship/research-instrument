"""Unit tests for make_manual_holding — the Add-manually helper (Fix 3)."""

from __future__ import annotations

from application.holdings_reader import Holding, make_manual_holding


def test_make_manual_holding_basic() -> None:
    """Helper builds a valid Holding with uppercased ticker and correct fields."""
    h = make_manual_holding(ticker="aapl", shares=10.0, cost_basis=1500.0)
    assert isinstance(h, Holding)
    assert h.ticker == "AAPL"
    assert h.shares == 10.0
    assert h.cost_basis == 1500.0
    assert h.account_type == "TFSA"  # default


def test_make_manual_holding_ticker_uppercased() -> None:
    """Ticker is uppercased regardless of input case."""
    assert make_manual_holding("msft", 5.0, 0.0).ticker == "MSFT"
    assert make_manual_holding("BrK-B", 1.0, 0.0).ticker == "BRK-B"


def test_make_manual_holding_custom_account_type() -> None:
    """account_type is passed through when supplied."""
    h = make_manual_holding("SPY", 3.0, 900.0, account_type="RRSP")
    assert h.account_type == "RRSP"


def test_make_manual_holding_zero_cost_basis() -> None:
    """Zero cost basis is valid (e.g. gifted shares)."""
    h = make_manual_holding("VOO", 2.0, 0.0)
    assert h.cost_basis == 0.0


def test_make_manual_holding_returns_frozen_dataclass() -> None:
    """Holding must be frozen (immutable)."""
    h = make_manual_holding("QQQ", 1.0, 200.0)
    try:
        h.ticker = "CHANGED"  # type: ignore[misc]
        raise AssertionError("Should have raised FrozenInstanceError")
    except Exception as exc:
        assert "frozen" in str(exc).lower() or "cannot assign" in str(exc).lower()


def test_make_manual_holding_whitespace_stripped_from_ticker() -> None:
    """Leading/trailing whitespace in ticker is stripped and uppercased."""
    h = make_manual_holding("  tsla  ", 1.0, 0.0)
    assert h.ticker == "TSLA"
