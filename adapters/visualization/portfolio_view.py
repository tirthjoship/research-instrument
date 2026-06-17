"""View-model for the portfolio tab: enrich holdings with live + brief data.

Adapter-side only — the domain ``Holding`` stays pure. Missing provider data
becomes DATA-GAP (None / "Unknown"), never fabricated.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from domain.models import Holding

_FLAG_ORDER = {"REDUCE": 0, "TRIM": 1, "REVIEW": 2}
_FLAGGED = set(_FLAG_ORDER)


@dataclass(frozen=True)
class PortfolioRow:
    ticker: str
    sector: str
    weight: float  # % of book value
    value: float  # market value $
    cost: float  # cost basis $
    pnl: float  # lifetime realised %
    today: float  # intraday %
    verdict: str  # "" = DATA-GAP
    why: str
    dividend_yield: float | None  # None = DATA-GAP
    beta: float | None
    quantity: float


def _yield_of(info: dict[str, Any]) -> float | None:
    raw = info.get("dividendYield")
    if raw is None:
        raw = info.get("trailingAnnualDividendYield")
    if raw is None:
        return None
    val = float(raw)
    if val <= 0:
        return None
    # yfinance sometimes returns a fraction (0.012) vs percent (1.2)
    return val * 100.0 if val < 1.0 else val


def enrich_holdings(
    holdings: list[Holding],
    prices: dict[str, dict[str, float]],
    infos: dict[str, dict[str, Any]],
    brief_by_ticker: dict[str, dict[str, Any]],
) -> list[PortfolioRow]:
    raw: list[dict[str, Any]] = []
    total_value = 0.0
    for h in holdings:
        p = prices.get(h.symbol, {})
        price = float(p.get("price") or h.purchase_price)
        value = h.quantity * price
        total_value += value
        info = infos.get(h.symbol, {})
        brief = brief_by_ticker.get(h.symbol, {})
        beta_raw = info.get("beta")
        raw.append(
            {
                "ticker": h.symbol,
                "sector": str(info.get("sector") or "Unknown"),
                "value": value,
                "cost": h.quantity * h.purchase_price,
                "today": float(p.get("change_pct") or 0.0),
                "verdict": str(brief.get("verdict") or ""),
                "why": str(brief.get("why") or ""),
                "dividend_yield": _yield_of(info),
                "beta": float(beta_raw) if beta_raw is not None else None,
                "quantity": h.quantity,
            }
        )
    rows: list[PortfolioRow] = []
    for r in raw:
        weight = (r["value"] / total_value * 100.0) if total_value > 0 else 0.0
        pnl = ((r["value"] - r["cost"]) / r["cost"] * 100.0) if r["cost"] > 0 else 0.0
        rows.append(
            PortfolioRow(
                ticker=r["ticker"],
                sector=r["sector"],
                weight=weight,
                value=r["value"],
                cost=r["cost"],
                pnl=pnl,
                today=r["today"],
                verdict=r["verdict"],
                why=r["why"],
                dividend_yield=r["dividend_yield"],
                beta=r["beta"],
                quantity=r["quantity"],
            )
        )
    return rows


def top5_weight(rows: list[PortfolioRow]) -> float:
    return sum(sorted((r.weight for r in rows), reverse=True)[:5])


def split_flagged_healthy(
    rows: list[PortfolioRow],
) -> tuple[list[PortfolioRow], list[PortfolioRow]]:
    flagged = sorted(
        (r for r in rows if r.verdict in _FLAGGED),
        key=lambda r: _FLAG_ORDER[r.verdict],
    )
    healthy = [r for r in rows if r.verdict not in _FLAGGED]
    return flagged, healthy
