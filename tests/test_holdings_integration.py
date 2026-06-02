"""Integration test: holdings + monitoring pipeline end-to-end."""

from __future__ import annotations

from datetime import datetime

from application.monitor_holdings import MonitorHoldingsUseCase
from domain.models import Holding
from tests.fakes.fake_holdings import FakeHoldings


def test_full_monitoring_pipeline() -> None:
    """Multi-holding portfolio with mixed signals."""
    holdings = FakeHoldings()
    holdings.add_holding(
        Holding("AMD", 50.0, 100.0, "2026-05-01")
    )  # will trigger stop-loss
    holdings.add_holding(Holding("NVDA", 10.0, 900.0, "2026-04-01"))  # healthy
    holdings.add_holding(Holding("TSLA", 20.0, 200.0, "2026-03-01"))  # sentiment bad

    prices = {"AMD": 85.0, "NVDA": 1050.0, "TSLA": 190.0}
    sentiments = {"AMD": 0.1, "NVDA": 0.3, "TSLA": -0.8}

    use_case = MonitorHoldingsUseCase(
        holdings=holdings,
        get_current_price=lambda s: prices[s],
        stop_loss_threshold=-0.08,
        get_sentiment_score=lambda s: sentiments[s],
    )

    signals = use_case.execute(datetime(2026, 6, 1))

    # AMD: -15% → stop_loss (immediate)
    # TSLA: sentiment -0.8 → negative_sentiment (this_week)
    # NVDA: healthy, no signals
    amd_signals = [s for s in signals if s.symbol == "AMD"]
    tsla_signals = [s for s in signals if s.symbol == "TSLA"]
    nvda_signals = [s for s in signals if s.symbol == "NVDA"]

    assert len(amd_signals) == 1
    assert amd_signals[0].signal_type == "stop_loss"
    assert len(tsla_signals) == 1
    assert tsla_signals[0].signal_type == "negative_sentiment"
    assert len(nvda_signals) == 0
