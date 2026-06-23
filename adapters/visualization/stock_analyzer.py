"""Backward-compatibility shim — moved to adapters.visualization.analysis."""

from adapters.visualization.analysis import AnalysisResult, SectionScore, analyze_ticker
from adapters.visualization.analysis.loaders import find_supply_chain_group
from adapters.visualization.analysis.radar import (
    aggregate_insider_by_quarter,
    compute_signal_radar,
)
from adapters.visualization.analysis.scoring.growth import score_growth
from adapters.visualization.analysis.scoring.health import score_health
from adapters.visualization.analysis.scoring.ownership import score_ownership
from adapters.visualization.analysis.scoring.performance import score_performance
from adapters.visualization.analysis.scoring.sentiment import score_sentiment
from adapters.visualization.analysis.scoring.supply_chain import score_supply_chain
from adapters.visualization.analysis.scoring.valuation import score_valuation

# Private-name aliases for backward compatibility with existing tests
_compute_signal_radar = compute_signal_radar
_find_supply_chain_group = find_supply_chain_group
_score_growth = score_growth
_score_health = score_health
_score_ownership = score_ownership
_score_performance = score_performance
_score_sentiment = score_sentiment
_score_supply_chain = score_supply_chain
_score_valuation = score_valuation

__all__ = [
    "analyze_ticker",
    "AnalysisResult",
    "SectionScore",
    "aggregate_insider_by_quarter",
    "_compute_signal_radar",
    "_find_supply_chain_group",
    "_score_growth",
    "_score_health",
    "_score_ownership",
    "_score_performance",
    "_score_sentiment",
    "_score_supply_chain",
    "_score_valuation",
]
