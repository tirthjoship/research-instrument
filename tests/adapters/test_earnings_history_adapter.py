# tests/adapters/test_earnings_history_adapter.py
from unittest.mock import MagicMock, patch

import pandas as pd

from adapters.data.earnings_history_adapter import (
    EarningsHistory,
    _fetch_earnings_history_impl,
    parse_earnings_frame,
)


def test_parse_counts_beats_last_4():
    df = pd.DataFrame(
        {
            "EPS Estimate": [0.50, 0.40, 0.30, 0.20, 0.10],
            "Reported EPS": [0.55, 0.41, 0.33, 0.18, None],  # last row not yet reported
            "Surprise(%)": [10.0, 2.5, 9.2, -10.0, None],
        },
        index=pd.to_datetime(
            ["2026-04-01", "2026-02-01", "2025-11-01", "2025-08-01", "2026-07-01"]
        ),
    )
    hist = parse_earnings_frame(df)
    assert isinstance(hist, EarningsHistory)
    assert hist.total == 4
    assert hist.beats == 3  # +10, +2.5, +9.2 positive; -10 miss
    assert len(hist.quarters) == 4


def test_parse_empty_returns_none():
    assert parse_earnings_frame(pd.DataFrame()) is None
    assert parse_earnings_frame(None) is None


def test_fetch_retries_transient_failure_then_succeeds():
    """A single transient Yahoo hiccup must not surface as a permanent DATA-GAP."""
    df = pd.DataFrame(
        {
            "EPS Estimate": [0.50],
            "Reported EPS": [0.55],
            "Surprise(%)": [10.0],
        },
        index=pd.to_datetime(["2026-04-01"]),
    )
    calls = {"n": 0}

    def flaky_ticker(_symbol: str) -> MagicMock:
        calls["n"] += 1
        if calls["n"] == 1:
            raise Exception("transient 429")
        mock_ticker = MagicMock()
        mock_ticker.earnings_dates = df
        return mock_ticker

    with (
        patch("yfinance.Ticker", side_effect=flaky_ticker),
        patch("adapters.data.earnings_history_adapter._SLEEP"),
    ):
        result = _fetch_earnings_history_impl("AAPL")

    assert result is not None
    assert result.total == 1
    assert calls["n"] == 2


def test_fetch_returns_none_after_retries_exhausted():
    with (
        patch("yfinance.Ticker", side_effect=Exception("persistent error")),
        patch("adapters.data.earnings_history_adapter._SLEEP"),
    ):
        result = _fetch_earnings_history_impl("BADINPUT")

    assert result is None
