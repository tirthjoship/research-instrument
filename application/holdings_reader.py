"""Read a brokerage holdings CSV into domain-friendly Holding rows. Maps broker
symbols to yfinance tickers (TSX -> .TO, class shares dot -> dash). PRIVACY: this
only reads a local gitignored file; nothing is transmitted here."""

from __future__ import annotations

import csv
import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Holding:
    ticker: str
    shares: float
    cost_basis: float
    account_type: str


_TSX = {"TSX", "TSE", "XTSE"}
_TSXV = {"TSXV", "XTSX", "CVE"}


def _get(row: dict[str, str], name: str) -> str:
    for k, v in row.items():
        if k.strip().lower() == name:
            return (v or "").strip()
    return ""


def _to_yf(symbol: str, exchange: str) -> str:
    base = symbol.replace(".", "-")  # class shares: BRK.B -> BRK-B
    ex = exchange.upper()
    if ex in _TSX:
        return f"{base}.TO"
    if ex in _TSXV:
        return f"{base}.V"
    return base


def make_manual_holding(
    ticker: str,
    shares: float,
    cost_basis: float,
    account_type: str = "TFSA",
) -> Holding:
    """Build a Holding from user-supplied fields.

    Ticker is uppercased automatically.  ``account_type`` defaults to ``"TFSA"``.

    Args:
        ticker: Stock ticker symbol (will be uppercased).
        shares: Number of shares held.
        cost_basis: Total book value / cost basis in account currency.
        account_type: Account type label (e.g. "TFSA", "RRSP", "Non-reg").

    Returns:
        A frozen :class:`Holding` ready to append to ``st.session_state["book"]``.
    """
    return Holding(
        ticker=ticker.upper().strip(),
        shares=shares,
        cost_basis=cost_basis,
        account_type=account_type,
    )


def read_holdings(path: str) -> list[Holding]:
    """Parse the CSV; skip blank-symbol / non-numeric-quantity / zero-share rows."""
    if not os.path.exists(path):
        return []
    out: list[Holding] = []
    with open(path, newline="") as fh:
        for row in csv.DictReader(fh):
            sym = _get(row, "symbol")
            if not sym:
                continue
            try:
                shares = float(_get(row, "quantity").replace(",", ""))
            except ValueError:
                continue
            if shares == 0:
                continue
            try:
                cost = float(_get(row, "book value (cad)").replace(",", "") or 0)
            except ValueError:
                cost = 0.0
            out.append(
                Holding(
                    ticker=_to_yf(sym, _get(row, "exchange")),
                    shares=shares,
                    cost_basis=cost,
                    account_type=_get(row, "account type")
                    or _get(row, "account classification"),
                )
            )
    return out
