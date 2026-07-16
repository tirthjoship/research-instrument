"""Read a brokerage holdings CSV into domain-friendly Holding rows. Maps broker
symbols to yfinance tickers (TSX -> .TO, class shares dot -> dash). PRIVACY: this
only reads a local gitignored file; nothing is transmitted here."""

from __future__ import annotations

import csv
import os
from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from domain.models import Holding as DomainHolding


@dataclass(frozen=True)
class Holding:
    ticker: str
    shares: float
    cost_basis: float
    account_type: str


_TSX = {"TSX", "TSE", "XTSE"}
_TSXV = {"TSXV", "XTSX", "CVE"}
_NSE = {"NSE"}
_BSE = {"BSE"}


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
    if ex in _NSE:
        return f"{base}.NS"
    if ex in _BSE:
        return f"{base}.BO"
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


def aggregate_to_book(holdings: list[Holding]) -> list["DomainHolding"]:
    """Aggregate broker rows by ticker into domain Holdings for the portfolio view.

    A real book holds the same ticker across several accounts (FHSA, TFSA, …).
    The portfolio tab wants one row per stock, so shares and book value are summed
    per ticker and the purchase price is the book-value-weighted average
    (total_cost / total_shares).

    Rows whose aggregate cannot yield a positive purchase_price (zero/blank book
    value, e.g. a cash-like position) are dropped — domain ``Holding`` forbids a
    non-positive price, and we never fabricate one. ``purchase_date`` is left
    blank because the broker export carries no per-lot date; nothing in the
    portfolio view reads it.
    """
    from collections import defaultdict

    from domain.models import Holding as DomainHolding

    shares: dict[str, float] = defaultdict(float)
    cost: dict[str, float] = defaultdict(float)
    for h in holdings:
        shares[h.ticker] += h.shares
        cost[h.ticker] += h.cost_basis

    book: list[DomainHolding] = []
    for ticker, qty in shares.items():
        if qty <= 0 or cost[ticker] <= 0:
            continue
        book.append(
            DomainHolding(
                symbol=ticker,
                quantity=qty,
                purchase_price=cost[ticker] / qty,
                purchase_date="",
                notes="aggregated from holdings.csv",
            )
        )
    return book


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
