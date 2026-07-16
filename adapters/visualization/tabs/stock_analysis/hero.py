"""Hero masthead view-model + HTML builder (spec D1): identity, price, 52-wk range, grade."""

from __future__ import annotations

import html as _html
from dataclasses import dataclass
from typing import Any

from adapters.visualization.components.currency import (
    currency_for_ticker,
    currency_symbol,
)


@dataclass(frozen=True)
class HeroView:
    company_name: str
    ticker: str
    exchange: str
    sector: str
    as_of: str
    price: str
    change_label: str
    change_down: bool
    market_cap: str
    low: str
    high: str
    range_pct: int
    range_label: str
    grade_label: str


def _money(value: float, ticker: str) -> str:
    sym = currency_symbol(currency_for_ticker(ticker))
    return f"{sym}{value:,.2f}"


def _market_cap(value: float, ticker: str) -> str:
    sym = currency_symbol(currency_for_ticker(ticker))
    for cutoff, suffix in ((1e12, "T"), (1e9, "B"), (1e6, "M")):
        if abs(value) >= cutoff:
            return f"{sym}{value / cutoff:.2f}{suffix}"
    return f"{sym}{value:,.0f}"


def _range_label(pct: int) -> str:
    if pct >= 75:
        return "near high"
    if pct <= 25:
        return "near low"
    return "mid-range"


_EXCHANGE_NAMES = {
    "NMS": "NASDAQ",
    "NGM": "NASDAQ",
    "NCM": "NASDAQ",
    "NAS": "NASDAQ",
    "NYQ": "NYSE",
    "PCX": "NYSE Arca",
    "ASE": "NYSE American",
    "BTS": "Cboe BZX",
    "TOR": "TSX",
    "LSE": "LSE",
}


def _decode_exchange(code: Any) -> str:
    """Human exchange name from a yfinance code (NMS -> NASDAQ); pass through if unknown."""
    c = str(code or "").strip()
    return _EXCHANGE_NAMES.get(c, c or "—")


def build_hero_view(
    result: Any, *, grade: str | None = None, as_of: str = ""
) -> HeroView:
    info = getattr(result, "info", {}) or {}
    ticker = str(getattr(result, "ticker", "") or "")
    low = info.get("fiftyTwoWeekLow")
    high = info.get("fiftyTwoWeekHigh")
    price = float(getattr(result, "current_price", 0.0) or 0.0)
    if low is not None and high is not None and float(high) > float(low):
        pct = int(round((price - float(low)) / (float(high) - float(low)) * 100))
        pct = max(0, min(100, pct))
        low_s, high_s = _money(float(low), ticker), _money(float(high), ticker)
    else:
        pct, low_s, high_s = 0, "—", "—"
    chg = float(getattr(result, "change_pct", 0.0) or 0.0)
    arrow = "▼" if chg < 0 else "▲"
    grade_label = f"EVIDENCE GRADE {grade} · DESCRIPTIVE" if grade else "DESCRIPTIVE"
    return HeroView(
        company_name=str(getattr(result, "company_name", "") or ""),
        ticker=ticker,
        exchange=_decode_exchange(info.get("exchange")),
        # prefer the more specific industry (e.g. "Semiconductors") over the broad sector
        sector=str(info.get("industry") or getattr(result, "sector", "") or "—"),
        as_of=as_of,
        price=_money(price, ticker),
        change_label=f"{arrow} {chg:+.2f}% today",
        change_down=chg < 0,
        market_cap=_market_cap(
            float(getattr(result, "market_cap", 0.0) or 0.0), ticker
        ),
        low=low_s,
        high=high_s,
        range_pct=pct,
        range_label=_range_label(pct),
        grade_label=grade_label,
    )


def build_hero_html(view: HeroView) -> str:
    e = _html.escape
    eyebrow = f"{e(view.exchange)} · {e(view.sector)}"
    if view.as_of:
        eyebrow += f" · as of {e(view.as_of)}"
    chg_cls = "sa-chg dn" if view.change_down else "sa-chg"
    return (
        '<div class="sa-hero" id="sa-hero">'
        '<div class="sa-ribbon">RESEARCH_ONLY — surfaces attributed evidence · makes no trade call</div>'
        '<div class="sa-hbody">'
        '<div class="sa-htop"><div>'
        f'<div class="sa-eyebrow">{eyebrow}</div>'
        f'<div class="sa-coname">{e(view.company_name)} <span class="sa-tkr">{e(view.ticker)}</span></div>'
        "</div>"
        f'<div class="sa-grade"><span class="dot"></span>{e(view.grade_label)}</div>'
        "</div>"
        '<div class="sa-prow">'
        '<div style="display:flex;align-items:baseline;gap:13px">'
        f'<span class="sa-price">{e(view.price)}</span>'
        f'<span class="{chg_cls}">{e(view.change_label)}</span>'
        f'<span class="sa-metab">Mkt cap <b>{e(view.market_cap)}</b></span></div>'
        '<div class="sa-rngw"><div class="hd">'
        f'<span class="ttl">52-wk range · {e(view.range_label)}</span>'
        f'<span class="pct">{view.range_pct}%</span></div>'
        f'<div class="track"><div class="mk" style="left:{view.range_pct}%"></div></div>'
        f'<div class="ends"><span>{e(view.low)}</span><span>{e(view.high)}</span></div>'
        "</div></div></div></div>"
    )
