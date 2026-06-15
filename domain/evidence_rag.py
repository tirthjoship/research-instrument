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
