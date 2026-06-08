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
