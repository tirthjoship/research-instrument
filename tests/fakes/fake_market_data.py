"""Fake MarketDataPort implementation for testing."""

from datetime import datetime

from domain.models import Signal


class FakeMarketData:
    def __init__(
        self,
        signals: dict[str, list[Signal]] | None = None,
        ticker_info: dict[str, dict[str, float]] | None = None,
        options_summary: dict[str, dict[str, float]] | None = None,
        analyst_data: dict[str, dict[str, float]] | None = None,
    ) -> None:
        self._signals = signals or {}
        self._ticker_info = ticker_info or {}
        self._options = options_summary or {}
        self._analyst = analyst_data or {}

    def get_signals(
        self,
        symbol: str,
        prediction_time: datetime,
        start_date: datetime | None = None,
        end_date: datetime | None = None,
    ) -> list[Signal]:
        all_signals = self._signals.get(symbol, [])
        return [
            s
            for s in all_signals
            if s.timestamp <= prediction_time
            and (start_date is None or s.timestamp >= start_date)
            and (end_date is None or s.timestamp <= end_date)
        ]

    def get_ticker_info(self, symbol: str) -> dict[str, float]:
        return self._ticker_info.get(symbol, {})

    def get_options_summary(
        self, symbol: str, prediction_time: datetime
    ) -> dict[str, float] | None:
        return self._options.get(symbol)

    def get_analyst_data(
        self, symbol: str, prediction_time: datetime
    ) -> dict[str, float] | None:
        return self._analyst.get(symbol)

    def validate_point_in_time(self, prediction_time: datetime) -> None:
        pass
