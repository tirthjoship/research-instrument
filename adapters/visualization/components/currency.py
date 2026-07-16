"""Shared currency derivation/formatting — one source of truth so every tab
agrees on what currency a ticker's numbers are in. Derives currency purely
from the yfinance ticker suffix (no network call, no Holding-record lookup)
so it works identically whether the value came from a live fetch or a
committed screen snapshot.
"""

from __future__ import annotations

_SUFFIX_CURRENCY: dict[str, str] = {
    ".TO": "CAD",
    ".V": "CAD",
    ".NS": "INR",
    ".BO": "INR",
}

_CURRENCY_SYMBOLS: dict[str, str] = {
    "USD": "$",
    "CAD": "C$",
    "INR": "₹",
}


def currency_for_ticker(ticker: str) -> str:
    """Return the ISO 4217 currency code implied by a ticker's suffix.
    Defaults to USD for any ticker with no recognized suffix (including
    bare US tickers, which have none)."""
    for suffix, code in _SUFFIX_CURRENCY.items():
        if ticker.upper().endswith(suffix):
            return code
    return "USD"


def currency_symbol(code: str) -> str:
    """Return the display symbol for a currency code. Falls back to the
    code itself (e.g. "EUR") for anything not in _CURRENCY_SYMBOLS — never
    silently defaults to "$", which would misrepresent the actual currency."""
    return _CURRENCY_SYMBOLS.get(code, code)


def format_money(
    value: float, ticker: str, *, decimals: int = 2, thousands: bool = False
) -> str:
    """Format *value* with the correct currency symbol for *ticker*."""
    code = currency_for_ticker(ticker)
    symbol = currency_symbol(code)
    if thousands:
        return f"{symbol}{value:,.{decimals}f}"
    return f"{symbol}{value:.{decimals}f}"
