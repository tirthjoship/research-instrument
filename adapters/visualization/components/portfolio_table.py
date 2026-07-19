"""Healthy-holdings table: pure sort/filter/page logic + HTML builder."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

from adapters.visualization.components.currency import (
    currency_for_ticker,
    currency_symbol,
)
from adapters.visualization.components.tooltip import tooltip
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


_PILL = {
    "HOLD": ("#F0FDF4", "#166534"),
    "ADD_OK": ("#ECFDF5", "#065F46"),
}


def _pill(verdict: str) -> str:
    bg, fg = _PILL.get(verdict, ("#F1F5F9", "#475569"))
    return (
        f'<span style="padding:2px 8px;border-radius:11px;font-size:.66rem;'
        f'font-weight:700;background:{bg};color:{fg};">{verdict}</span>'
    )


def _row_html(r: PortfolioRow, show_more: bool) -> str:
    pnl_c = "#16A34A" if r.pnl >= 0 else "#DC2626"
    today_c = "#16A34A" if r.today >= 0 else "#DC2626"
    sym = currency_symbol(currency_for_ticker(r.ticker))
    cells = [
        f"<td style=\"font-family:'Fraunces',serif;font-weight:700;"
        f'color:var(--ri-teal);">{r.ticker}</td>',
        f"<td>{r.sector}</td>",
        f"<td style=\"text-align:right;font-family:'IBM Plex Mono',monospace;\">"
        f'<span style="display:inline-block;height:7px;border-radius:3px;background:#CBD5E1;'
        f'width:{r.weight*4.5:.0f}px;margin-right:6px;vertical-align:middle;"></span>{r.weight:.1f}%</td>',
        f"<td style=\"text-align:right;font-family:'IBM Plex Mono',monospace;\">{sym}{r.value:,.0f}</td>",
        f"<td style=\"text-align:right;font-family:'IBM Plex Mono',monospace;color:{pnl_c};\">"
        f'{"+" if r.pnl>=0 else ""}{r.pnl:.1f}%</td>',
        f"<td style=\"text-align:right;font-family:'IBM Plex Mono',monospace;color:{today_c};\">"
        f'{"+" if r.today>=0 else ""}{r.today:.1f}%</td>',
    ]
    if show_more:
        yld = f"{r.dividend_yield:.2f}%" if r.dividend_yield is not None else "—"
        beta = f"{r.beta:.2f}" if r.beta is not None else "—"
        cells.append(
            f"<td style=\"text-align:right;font-family:'IBM Plex Mono',monospace;\">{yld}</td>"
        )
        cells.append(
            f"<td style=\"text-align:right;font-family:'IBM Plex Mono',monospace;\">{beta}</td>"
        )
        cells.append(
            f"<td style=\"text-align:right;font-family:'IBM Plex Mono',monospace;\">{sym}{r.cost:,.0f}</td>"
        )
    cells.append(f"<td>{_pill(r.verdict)}</td>")
    return "<tr>" + "".join(cells) + "</tr>"


def build_table_html(rows: list[PortfolioRow], state: TableState) -> str:
    heads = ["Ticker", "Sector", "Weight", "Value", "P&amp;L %", "Today"]
    if state.show_more:
        heads += [
            f"{tooltip('Dividend yield', 'Yield')}",
            f"{tooltip('Beta', 'Beta')}",
            "Cost",
        ]
    heads.append("Verdict")
    thead = "".join(
        f'<th style="text-align:left;font-size:.65rem;text-transform:uppercase;'
        f"letter-spacing:.04em;color:var(--ri-muted);padding:7px 9px;"
        f'border-bottom:1px solid var(--ri-line);">{h}</th>'
        for h in heads
    )
    body = "".join(_row_html(r, state.show_more) for r in rows)
    return (
        '<table style="width:100%;border-collapse:collapse;font-size:.82rem;background:#fff;'
        'border-radius:10px;overflow:hidden;">'
        f"<thead><tr>{thead}</tr></thead><tbody>{body}</tbody></table>"
    )
