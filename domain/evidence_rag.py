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
