"""Tests for the shared currency-formatting module (multi-market Phase 2)."""

from __future__ import annotations

from adapters.visualization.components.currency import (
    currency_for_ticker,
    currency_symbol,
    format_money,
)


def test_currency_for_ticker_us_default():
    assert currency_for_ticker("AAPL") == "USD"


def test_currency_for_ticker_canada():
    assert currency_for_ticker("RY.TO") == "CAD"
    assert currency_for_ticker("SHOP.V") == "CAD"


def test_currency_for_ticker_india():
    assert currency_for_ticker("RELIANCE.NS") == "INR"
    assert currency_for_ticker("TCS.BO") == "INR"


def test_currency_symbol_known_codes():
    assert currency_symbol("USD") == "$"
    assert currency_symbol("CAD") == "C$"
    assert currency_symbol("INR") == "₹"


def test_currency_symbol_unknown_code_falls_back_to_code_itself():
    """Never silently show '$' for a currency we don't recognize — that's
    exactly the wrong-currency-sign bug this module exists to prevent."""
    assert currency_symbol("EUR") == "EUR"


def test_format_money_us_no_thousands():
    assert format_money(1234.5, "AAPL") == "$1234.50"


def test_format_money_canada_with_thousands():
    assert format_money(1234.5, "RY.TO", thousands=True) == "C$1,234.50"


def test_format_money_india():
    assert format_money(999.99, "RELIANCE.NS") == "₹999.99"
