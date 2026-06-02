"""Fake HoldingsPort for testing."""

from __future__ import annotations

from domain.models import Holding


class FakeHoldings:
    def __init__(self) -> None:
        self._holdings: dict[str, Holding] = {}

    def add_holding(self, holding: Holding) -> None:
        self._holdings[holding.symbol] = holding

    def remove_holding(self, symbol: str) -> None:
        self._holdings.pop(symbol, None)

    def get_holdings(self) -> list[Holding]:
        return list(self._holdings.values())

    def get_holding(self, symbol: str) -> Holding | None:
        return self._holdings.get(symbol)
