"""Tests for PortfolioVerdictUseCase."""

from datetime import datetime, timedelta, timezone


def _series(start: datetime, vals: list[int]) -> list[tuple[datetime, float]]:
    return [(start + timedelta(days=i), float(v)) for i, v in enumerate(vals)]


def test_verdict_exit_for_broken_trend() -> None:
    from application.portfolio_verdict import PortfolioVerdictUseCase

    start = datetime(2024, 1, 1, tzinfo=timezone.utc)
    vals = list(range(100, 350)) + list(range(350, 250, -1))
    uc = PortfolioVerdictUseCase(price_provider=lambda t: _series(start, vals))
    row = uc.verdict_for("RIVN")
    assert row["verdict"] in {"EXIT", "TRIM"}
    assert row["trend_intact"] is False


def test_verdict_hold_for_intact_uptrend() -> None:
    from application.portfolio_verdict import PortfolioVerdictUseCase

    start = datetime(2024, 1, 1, tzinfo=timezone.utc)
    vals = list(range(100, 400))  # steady uptrend
    uc = PortfolioVerdictUseCase(price_provider=lambda t: _series(start, vals))
    row = uc.verdict_for("MU")
    assert row["verdict"] == "HOLD"
    assert row["trend_intact"] is True
    assert row["trailing_stop"] is not None
