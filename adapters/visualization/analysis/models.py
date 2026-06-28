"""Dataclasses for stock analysis results."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Literal

if TYPE_CHECKING:
    from application.analyst_panel import AnalystPanel
    from application.news_context import NewsContext


@dataclass
class SectionScore:
    """Score for one analysis section (e.g., Valuation 4/6)."""

    title: str
    score: int
    max_score: int
    summary: str
    verdicts: list[tuple[Literal["pass", "warn", "fail"], str]]


@dataclass
class AnalysisResult:
    """Complete analysis result for one ticker."""

    ticker: str
    company_name: str
    current_price: float
    change_pct: float
    market_cap: float
    sector: str

    # Signal radar scores (0-10 per dimension)
    signal_scores: dict[str, float] = field(default_factory=dict)

    # Overall verdict
    grade: str = "hold"
    conviction: float = 5.0
    hold_duration: str = "Monitor daily"

    # Analyst consensus
    analyst_count: int = 0
    analyst_mean_target: float = 0.0
    analyst_recommendation: str = ""

    # Per-section scores
    valuation: SectionScore | None = None
    growth: SectionScore | None = None
    performance: SectionScore | None = None
    health: SectionScore | None = None
    ownership: SectionScore | None = None
    sentiment: SectionScore | None = None
    supply_chain: SectionScore | None = None

    # Raw data for charts
    info: dict[str, Any] = field(default_factory=dict)
    quarterly_financials: Any = None
    quarterly_balance_sheet: Any = None
    quarterly_cashflow: Any = None
    insider_transactions: list[dict[str, Any]] = field(default_factory=list)
    buzz_signals: list[Any] = field(default_factory=list)
    recommendation_data: Any = None
    peer_data: list[dict[str, Any]] = field(default_factory=list)
    supply_chain_group: dict[str, Any] | None = None

    # E1: Industry-relative percentiles (metric -> 0-100 or None for DATA_GAP)
    peer_percentiles: dict[str, float | None] = field(default_factory=dict)

    # E2: Attributed third-party analyst panel (None if import fails)
    analyst_panel: "AnalystPanel | None" = None

    # E3: Attributed news/event context (None if no signals)
    news_context: "NewsContext | None" = None
