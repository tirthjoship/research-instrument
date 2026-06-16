# tests/adapters/test_earnings_history_adapter.py
import pandas as pd

from adapters.data.earnings_history_adapter import EarningsHistory, parse_earnings_frame


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
