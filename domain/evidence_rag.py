"""Pure RAG evidence classification (stdlib only). No framework imports."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

DIMENSIONS: tuple[str, ...] = (
    "Technicals",
    "Valuation",
    "Financials",
    "Earnings",
    "Analysts",
)


class RagColor(Enum):
    RED = "R"
    AMBER = "A"
    GREEN = "G"
    GAP = "GAP"


@dataclass(frozen=True)
class RagSignal:
    dimension: str
    color: RagColor
    detail: str


def _fmt(v: float | None, suffix: str = "") -> str:
    return "—" if v is None else f"{v:+.1f}{suffix}"


def classify_technicals(
    atr_vs_200d: float | None, vs_spy_pct: float | None
) -> RagSignal:
    if atr_vs_200d is None and vs_spy_pct is None:
        return RagSignal("Technicals", RagColor.GAP, "DATA-GAP: no price history")
    detail = f"{_fmt(atr_vs_200d)} ATR vs 200-day · vs SPY {_fmt(vs_spy_pct, '%')}"
    if atr_vs_200d is None:
        return RagSignal("Technicals", RagColor.AMBER, detail)
    if atr_vs_200d >= 0.5:
        return RagSignal("Technicals", RagColor.GREEN, detail)
    if atr_vs_200d <= -1.5:
        return RagSignal("Technicals", RagColor.RED, detail)
    return RagSignal("Technicals", RagColor.AMBER, detail)


def classify_valuation(
    peg: float | None, pe: float | None, sector_pctile: float | None
) -> RagSignal:
    if peg is None and pe is None and sector_pctile is None:
        return RagSignal("Valuation", RagColor.GAP, "DATA-GAP: no valuation data")
    parts = []
    if peg is not None:
        parts.append(f"PEG {peg:.1f}")
    if pe is not None:
        parts.append(f"P/E {pe:.0f}")
    if sector_pctile is not None:
        parts.append(f"cheaper than {sector_pctile:.0f}% of sector")
    detail = " · ".join(parts)
    cheap = (peg is not None and peg <= 1.2) or (
        sector_pctile is not None and sector_pctile >= 60
    )
    rich = (peg is not None and peg >= 2.5) or (
        sector_pctile is not None and sector_pctile <= 25
    )
    if cheap and not rich:
        return RagSignal("Valuation", RagColor.GREEN, detail)
    if rich and not cheap:
        return RagSignal("Valuation", RagColor.RED, detail)
    return RagSignal("Valuation", RagColor.AMBER, detail)


def classify_financials(
    fcf_positive: bool | None,
    debt_to_equity: float | None,
    margins_stable: bool | None,
) -> RagSignal:
    if fcf_positive is None and debt_to_equity is None and margins_stable is None:
        return RagSignal("Financials", RagColor.GAP, "DATA-GAP: no financials")
    fcf_txt = (
        "FCF positive"
        if fcf_positive
        else ("FCF negative" if fcf_positive is False else "FCF —")
    )
    debt_txt = (
        "debt —"
        if debt_to_equity is None
        else ("debt high" if debt_to_equity >= 150 else "debt moderate")
    )
    margin_txt = (
        "margins stable"
        if margins_stable
        else ("margins —" if margins_stable is None else "margins soft")
    )
    detail = f"{fcf_txt} · {debt_txt} · {margin_txt}"
    levered = debt_to_equity is not None and debt_to_equity >= 150
    if fcf_positive and not levered:
        return RagSignal("Financials", RagColor.GREEN, detail)
    if fcf_positive is False or levered:
        return RagSignal("Financials", RagColor.RED, detail)
    return RagSignal("Financials", RagColor.AMBER, detail)


def classify_earnings(beats: int | None, total: int | None) -> RagSignal:
    if total is None or total == 0:
        return RagSignal("Earnings", RagColor.GAP, "DATA-GAP: no earnings history")
    b = beats or 0
    detail = f"EPS beat {b} of {total} · revenue surprise: needs estimates feed"
    ratio = b / total
    if ratio >= 0.75:
        return RagSignal("Earnings", RagColor.GREEN, detail)
    if ratio <= 0.25:
        return RagSignal("Earnings", RagColor.RED, detail)
    return RagSignal("Earnings", RagColor.AMBER, detail)


def classify_analysts(
    count: int,
    target_mean: float | None,
    target_high: float | None,
    target_low: float | None,
    data_gap: bool,
    current_price: float | None,
) -> RagSignal:
    if data_gap or target_mean is None:
        return RagSignal("Analysts", RagColor.GAP, "DATA-GAP: no analyst coverage")
    pieces = [f"{count} cover"]
    upside = None
    if current_price and current_price > 0:
        upside = (target_mean - current_price) / current_price
        pieces.append(f"target {upside:+.0%}")
    spread = None
    if target_high is not None and target_low is not None and target_mean:
        spread = (target_high - target_low) / target_mean
        pieces.append("wide spread" if spread >= 0.30 else "tight spread")
    detail = " · ".join(pieces)
    if spread is not None and spread >= 0.30:
        return RagSignal("Analysts", RagColor.AMBER, detail)
    if upside is None:
        return RagSignal("Analysts", RagColor.AMBER, detail)
    return RagSignal(
        "Analysts", RagColor.GREEN if upside >= 0 else RagColor.RED, detail
    )
