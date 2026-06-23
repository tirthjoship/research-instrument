"""Stock analysis package."""

from adapters.visualization.analysis.analyze import analyze_ticker
from adapters.visualization.analysis.models import AnalysisResult, SectionScore
from adapters.visualization.analysis.radar import aggregate_insider_by_quarter

__all__ = [
    "analyze_ticker",
    "AnalysisResult",
    "SectionScore",
    "aggregate_insider_by_quarter",
]
