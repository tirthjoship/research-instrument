"""Healthy-holdings table: pure sort/filter/page logic + HTML builder."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

from adapters.visualization.portfolio_view import PortfolioRow

_SORT_KEY: dict[str, Callable[[PortfolioRow], Any]] = {
    "ticker": lambda r: r.ticker,
    "sector": lambda r: r.sector,
    "weight": lambda r: r.weight,
    "value": lambda r: r.value,
    "pnl": lambda r: r.pnl,
    "today": lambda r: r.today,
    "yield": lambda r: (r.dividend_yield if r.dividend_yield is not None else -1.0),
    "beta": lambda r: (r.beta if r.beta is not None else -1.0),
}


@dataclass(frozen=True)
class TableState:
    sort: str = "weight"
    ascending: bool = False
    filter: str = "all"  # all | gain | loss
    query: str = ""
    page: int = 1
    show_more: bool = False


def apply_table_state(
    rows: list[PortfolioRow], state: TableState
) -> list[PortfolioRow]:
    out = list(rows)
    if state.query:
        q = state.query.upper()
        out = [r for r in out if q in r.ticker.upper()]
    if state.filter == "gain":
        out = [r for r in out if r.pnl > 0]
    elif state.filter == "loss":
        out = [r for r in out if r.pnl < 0]
    key = _SORT_KEY.get(state.sort, _SORT_KEY["weight"])
    out.sort(key=key, reverse=not state.ascending)
    return out
