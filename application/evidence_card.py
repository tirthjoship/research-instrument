"""Assemble the 5 RAG signals + sparkline for one ticker. Composes domain + adapters."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from adapters.data.earnings_history_adapter import EarningsHistory
from application.analyst_panel import AnalystPanel
from domain.evidence_rag import (
    DIMENSIONS,
    RagSignal,
    classify_analysts,
    classify_earnings,
    classify_financials,
    classify_technicals,
    classify_valuation,
)
from domain.peer_relative import sector_percentile


@dataclass(frozen=True)
class EvidenceCard:
    ticker: str
    signals: tuple[RagSignal, ...]  # length 5, DIMENSIONS order
    sparkline: tuple[float, ...]  # realized closes (~90d), no projection


def build_evidence_card(
    ticker: str,
    *,
    info: dict[str, Any],
    prices: dict[str, Any],
    panel: AnalystPanel,
    earnings: EarningsHistory | None,
    peers: list[float | None],
) -> EvidenceCard:
    cur = info.get("current_price")
    atr = prices.get("atr")
    ma200 = prices.get("ma200")
    atr_vs_200d = None
    if atr and ma200 and cur is not None and atr != 0:
        atr_vs_200d = (cur - ma200) / atr
    technicals = classify_technicals(atr_vs_200d, prices.get("book_1y"))

    pe = info.get("trailing_pe")
    pct = sector_percentile(pe, peers) if pe is not None and peers else None
    valuation = classify_valuation(info.get("peg_ratio"), pe, pct)

    fcf = info.get("free_cashflow")
    financials = classify_financials(
        None if fcf is None else fcf > 0,
        info.get("debt_to_equity"),
        None,  # margins_stable: left None until a margin-trend source exists
    )

    earnings_sig = classify_earnings(
        earnings.beats if earnings else None, earnings.total if earnings else None
    )

    analysts = classify_analysts(
        panel.count,
        panel.target_mean,
        panel.target_high,
        panel.target_low,
        panel.data_gap,
        cur,
    )

    by_name = {
        s.dimension: s
        for s in (technicals, valuation, financials, earnings_sig, analysts)
    }
    signals = tuple(by_name[d] for d in DIMENSIONS)

    closes = prices.get("closes") or []
    sparkline = tuple(float(c) for c in closes[-90:])
    return EvidenceCard(ticker=ticker, signals=signals, sparkline=sparkline)
