"""Use cases: orchestration of domain and adapters."""

from datetime import datetime

from domain.models import BacktestResult, Sentiment, Signal
from domain.ports import BacktestResultPort, MarketDataPort, SentimentPort, StockPredictorPort


def run_backtest(
    market_data: MarketDataPort,
    sentiment_port: SentimentPort,
    predictor: StockPredictorPort,
    results_port: BacktestResultPort,
    symbol: str,
    prediction_time: datetime,
) -> BacktestResult:
    """Run a single point-in-time backtest step.

    Args:
        market_data: Source implementing MarketDataPort.
        sentiment_port: Source implementing SentimentPort.
        predictor: Model implementing StockPredictorPort.
        results_port: Sink implementing BacktestResultPort.
        symbol: Ticker symbol.
        prediction_time: As-of time (no future data).

    Returns:
        BacktestResult for this run.
    """
    signals = market_data.get_signals(symbol, prediction_time)
    sentiments = sentiment_port.get_sentiment(symbol, prediction_time)
    # TODO: validate_point_in_time_access, call predictor.predict, build BacktestResult
    # results_port.save_result(result)
    raise NotImplementedError("Skeleton only")


def run_post_mortem_analysis(
    results_port: BacktestResultPort,
    start_date: datetime,
    end_date: datetime,
) -> dict[str, object]:
    """Analyze failed predictions for recursive learning.

    Args:
        results_port: Source of backtest results.
        start_date: Start of analysis window.
        end_date: End of analysis window.

    Returns:
        Failure patterns (e.g. sector, sentiment divergence) for feedback.
    """
    # TODO: get results, identify failures, extract patterns
    return {}
