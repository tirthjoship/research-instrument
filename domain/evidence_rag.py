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
