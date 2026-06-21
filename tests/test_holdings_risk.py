from datetime import datetime, timedelta, timezone


def _series(start, vals):
    return [(start + timedelta(days=i), float(v)) for i, v in enumerate(vals)]


def test_assess_flags_broken_trend_loser_as_reduce():
    from application.holdings_reader import Holding
    from application.holdings_risk import HoldingsRiskAssessmentUseCase
    from application.narrator import FakeNarrator
    from domain.discipline import Verdict

    start = datetime(2023, 1, 1, tzinfo=timezone.utc)
    name_vals = list(range(100, 360)) + list(range(360, 200, -1))
    spy_vals = list(range(100, 100 + len(name_vals)))
    series = {"WEAK": _series(start, name_vals), "SPY": _series(start, spy_vals)}

    def provider(t):
        return series.get(t, [])

    holdings = [
        Holding(ticker="WEAK", shares=10.0, cost_basis=3000.0, account_type="TFSA")
    ]
    uc = HoldingsRiskAssessmentUseCase(
        price_provider=provider, narrator=FakeNarrator("why")
    )
    report = uc.execute(holdings, start, start + timedelta(days=len(name_vals)))
    pos = report["positions"][0]
    assert pos.ticker == "WEAK"
    assert pos.verdict in (Verdict.REDUCE, Verdict.REVIEW)
    assert report["portfolio"].n_positions == 1
    assert pos.why == "why"


def test_assess_handles_naive_provider_datetimes():
    # Regression: live yfinance returns tz-naive datetimes while callers pass
    # tz-aware bounds; the use case must normalize instead of raising TypeError.
    from datetime import datetime as _dt

    from application.holdings_reader import Holding
    from application.holdings_risk import HoldingsRiskAssessmentUseCase
    from application.narrator import FakeNarrator

    naive_start = _dt(2023, 1, 1)  # tz-naive, as a price provider would return
    name_vals = list(range(100, 360)) + list(range(360, 200, -1))
    spy_vals = list(range(100, 100 + len(name_vals)))
    series = {
        "WEAK": _series(naive_start, name_vals),
        "SPY": _series(naive_start, spy_vals),
    }

    uc = HoldingsRiskAssessmentUseCase(
        price_provider=lambda t: series.get(t, []), narrator=FakeNarrator("why")
    )
    aware_start = datetime(2023, 1, 1, tzinfo=timezone.utc)  # tz-aware bounds
    report = uc.execute(
        [Holding(ticker="WEAK", shares=10.0, cost_basis=3000.0, account_type="TFSA")],
        aware_start,
        aware_start + timedelta(days=len(name_vals)),
    )
    assert report["portfolio"].n_positions == 1


def test_assess_empty_holdings():
    from application.holdings_risk import HoldingsRiskAssessmentUseCase
    from application.narrator import FakeNarrator

    uc = HoldingsRiskAssessmentUseCase(
        price_provider=lambda t: [], narrator=FakeNarrator()
    )
    start = datetime(2023, 1, 1, tzinfo=timezone.utc)
    report = uc.execute([], start, start + timedelta(days=10))
    assert report["positions"] == []
    assert report["portfolio"].n_positions == 0


def test_vol_numpy_floats_do_not_crash():
    """Regression: statistics.pstdev raises AttributeError on numpy scalars
    in Python 3.12. _vol() must coerce before calling pstdev."""
    from datetime import datetime, timedelta, timezone

    import numpy as np

    from application.holdings_reader import Holding
    from application.holdings_risk import HoldingsRiskAssessmentUseCase
    from application.narrator import FakeNarrator

    # Build a price series with enough history using numpy floats
    # (as yfinance returns via daily_returns)
    numpy_prices = [np.float64(100.0 + i * 0.5) for i in range(260)]
    start = datetime(2023, 1, 1, tzinfo=timezone.utc)
    series = {
        "AAPL": [(start + timedelta(days=i), v) for i, v in enumerate(numpy_prices)],
        "SPY": [(start + timedelta(days=i), 100.0 + i * 0.3) for i in range(260)],
    }

    uc = HoldingsRiskAssessmentUseCase(
        price_provider=lambda t: series.get(t, []), narrator=FakeNarrator("why")
    )
    # Must not raise AttributeError: 'float' object has no attribute 'numerator'
    result = uc.execute(
        [Holding(ticker="AAPL", shares=10.0, cost_basis=2000.0, account_type="TFSA")],
        start,
        start + timedelta(days=259),
    )
    assert result["portfolio"].n_positions == 1


def test_top_concentration_uses_market_value_not_price():
    """top_concentration must use market_value_cad, not per-share price.

    Two positions:
      - HIGH_PRICE: 1 share @ $1000/share  → market_value_cad = 1000.0
      - HIGH_MV:  100 shares @ $50/share   → market_value_cad = 5000.0

    Correct (market-value) top_concentration = 5000 / 6000 ≈ 0.8333…
    Buggy  (price-based)   top_concentration = 1000 / 1050 ≈ 0.9524…
    """
    from application.holdings_risk import HoldingsRiskAssessmentUseCase
    from application.narrator import FakeNarrator
    from domain.discipline import Verdict
    from domain.models import PositionRisk

    def _pos(ticker: str, price: float, market_value_cad: float) -> PositionRisk:
        return PositionRisk(
            ticker=ticker,
            price=price,
            verdict=Verdict.HOLD,
            confidence=0.6,
            trend_health=1.0,
            vol_signal=0.0,
            relative_strength=0.0,
            downside_to_stop=0.1,
            upside_to_recover=0.2,
            behavior_flags=(),
            unrealized_pct=0.0,
            account_type="TFSA",
            abstained=False,
            why="test",
            quantity=1.0,
            market_value_cad=market_value_cad,
        )

    positions = [
        _pos("HIGH_PRICE", price=1000.0, market_value_cad=1000.0),  # 1 share
        _pos("HIGH_MV", price=50.0, market_value_cad=5000.0),  # 100 shares
    ]

    uc = HoldingsRiskAssessmentUseCase(
        price_provider=lambda t: [], narrator=FakeNarrator()
    )
    result = uc._portfolio(positions)  # type: ignore[attr-defined]

    expected = 5000.0 / 6000.0  # ≈ 0.8333…
    assert abs(result.top_concentration - expected) < 1e-9, (
        f"Expected top_concentration ≈ {expected:.6f} (market-value based), "
        f"got {result.top_concentration:.6f} — still using per-share price?"
    )
