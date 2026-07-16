from datetime import datetime, timedelta, timezone

from application.opportunity_scan_use_case import OpportunityScanUseCase
from domain.models import BuzzSignal, Signal
from domain.surfaced_call import OpportunityDirection
from domain.universe import UniverseEntry
from tests.fakes.fake_buzz_discovery import FakeBuzzDiscovery
from tests.fakes.fake_market_data import FakeMarketData
from tests.fakes.fake_surfaced_call_store import FakeSurfacedCallStore
from tests.fakes.fake_universe_provider import FakeUniverseProvider

NOW = datetime(2026, 6, 5, tzinfo=timezone.utc)


def _prices(symbol):
    return [
        Signal(
            symbol=symbol,
            timestamp=NOW - timedelta(days=39 - i),
            price=100.0,
            volume=1.0,
            open_=100.0,
            high=100.0,
            low=100.0,
        )
        for i in range(40)
    ]


def _md():
    return FakeMarketData(
        signals={
            "ASTS": _prices("ASTS"),
            "DUD": _prices("DUD"),
            "SPY": _prices("SPY"),
            "QQQ": _prices("QQQ"),
        },
        ticker_info={"ASTS": {"marketCap": 3e9}, "DUD": {"marketCap": 5e8}},
    )


def _buzz_sig(ticker, days_ago):
    return BuzzSignal(
        ticker=ticker,
        source="reddit",
        sentiment_raw=0.7,
        fetched_at=NOW - timedelta(days=days_ago),
        mention_count=1,
        scorer="keyword",
        article_hash=f"h{days_ago}",
    )


def _conviction(high_ticker):
    def fn(ticker, now):
        if ticker == high_ticker:
            return 8.0, {"event_signal": 9.0, "smart_money": 7.0}
        return 3.0, {"event_signal": 3.0}

    return fn


def test_surfaces_qualifying_name_and_abstains_on_rest():
    buzz = FakeBuzzDiscovery([_buzz_sig("ASTS", d) for d in (1, 2, 3, 4, 5)])
    store = FakeSurfacedCallStore()
    uc = OpportunityScanUseCase(
        universe_provider=FakeUniverseProvider(
            [UniverseEntry("ASTS", "space"), UniverseEntry("DUD", "space")]
        ),
        conviction_provider=_conviction("ASTS"),
        buzz_discovery=buzz,
        market_data=_md(),
        store=store,
        cmin=6.0,
        dmin=6.0,
    )
    calls = uc.execute(NOW)
    assert [c.ticker for c in calls] == ["ASTS"]
    assert calls[0].direction is OpportunityDirection.BUY
    assert any(e.dimension == "divergence" for e in calls[0].evidence)
    assert store.saved and store.saved[0].ticker == "ASTS"


def test_naive_stored_timestamps_with_aware_now_does_not_crash():
    """Regression: stored buzz/price timestamps are tz-naive (SQLite, yfinance),
    but the CLI passes a tz-aware UTC `now`. The divergence path compared them
    directly and raised TypeError ("can't compare offset-naive and offset-aware
    datetimes"), crashing the live scan. The use case must normalize inbound
    timestamps to `now`'s awareness."""
    naive_now = NOW.replace(tzinfo=None)
    # Buzz signals come from SQLite with tz-naive `fetched_at` (the real culprit).
    naive_buzz = [
        BuzzSignal(
            ticker="ASTS",
            source="reddit",
            sentiment_raw=0.7,
            fetched_at=naive_now - timedelta(days=d),
            mention_count=1,
            scorer="keyword",
            article_hash=f"h{d}",
        )
        for d in (1, 2, 3, 4, 5)
    ]
    store = FakeSurfacedCallStore()
    uc = OpportunityScanUseCase(
        universe_provider=FakeUniverseProvider([UniverseEntry("ASTS", "space")]),
        conviction_provider=_conviction("ASTS"),
        buzz_discovery=FakeBuzzDiscovery(naive_buzz),
        market_data=_md(),
        store=store,
        cmin=6.0,
        dmin=6.0,
    )
    # aware now + naive stored data must not raise
    calls = uc.execute(NOW)
    assert [c.ticker for c in calls] == ["ASTS"]


def test_scan_persists_full_candidate_distribution():
    """All universe candidates are logged with surfaced flag; only ASTS passes cmin.

    ASTS is given 25 days of attention history so it clears the min-history gate
    (default 21 days). DUD has no attention history so it stays ineligible.
    """
    from domain.models import AttentionPoint
    from tests.fakes.fake_attention_series import FakeAttentionSeries

    asts_attention = [
        AttentionPoint("ASTS", NOW - timedelta(days=d), 5.0, "google_trends")
        for d in range(25)
    ]
    store = FakeSurfacedCallStore()
    uc = OpportunityScanUseCase(
        universe_provider=FakeUniverseProvider(
            [UniverseEntry("ASTS", "space"), UniverseEntry("DUD", "space")]
        ),
        conviction_provider=_conviction("ASTS"),
        buzz_discovery=FakeBuzzDiscovery(
            [_buzz_sig("ASTS", d) for d in (1, 2, 3, 4, 5)]
        ),
        market_data=_md(),
        store=store,
        attention_provider=FakeAttentionSeries(asts_attention),
        cmin=6.0,
        dmin=0.0,
    )
    uc.execute(NOW)
    assert len(store.candidates) == 2
    surfaced_flags = {c["ticker"]: c["surfaced"] for c in store.candidates}
    assert surfaced_flags["ASTS"] is True
    assert surfaced_flags["DUD"] is False


def test_abstention_returns_empty():
    store = FakeSurfacedCallStore()
    uc = OpportunityScanUseCase(
        universe_provider=FakeUniverseProvider([UniverseEntry("DUD", "space")]),
        conviction_provider=_conviction("NONE"),
        buzz_discovery=FakeBuzzDiscovery([]),
        market_data=_md(),
        store=store,
        cmin=6.0,
        dmin=6.0,
    )
    assert uc.execute(NOW) == []
    assert store.saved == []


def test_scan_skips_thin_history_names():
    from domain.models import AttentionPoint
    from tests.fakes.fake_attention_series import FakeAttentionSeries

    NOW_T = datetime(2026, 6, 5, tzinfo=timezone.utc)
    thin = [AttentionPoint("NEW", NOW_T - timedelta(days=2), 9.0, "google_trends")]
    store = FakeSurfacedCallStore()
    uc = OpportunityScanUseCase(
        universe_provider=FakeUniverseProvider([UniverseEntry("NEW", "space")]),
        conviction_provider=lambda t, now: (9.0, {"smart_money": 9.0}),
        buzz_discovery=FakeBuzzDiscovery([]),
        market_data=FakeMarketData(
            signals={"NEW": [], "SPY": [], "QQQ": []},
            ticker_info={"NEW": {"market_cap": 3e9}},
        ),
        store=store,
        attention_provider=FakeAttentionSeries(thin),
        cmin=1.0,
        dmin=1.0,
        min_history_days=21,
    )
    uc.execute(NOW_T)
    # thin-history name is logged as a candidate but NOT surfaced
    assert all(not c["surfaced"] for c in store.candidates if c["ticker"] == "NEW")


def test_execute_uses_configured_benchmark_ticker():
    """OpportunityScanUseCase(benchmark_ticker=...) resolves spy_at_surface from
    that ticker's signals, not a hardcoded "SPY" key — needed so CA/India scans
    surface a real benchmark price instead of a missing/zero value."""
    buzz = FakeBuzzDiscovery([_buzz_sig("ASTS", d) for d in (1, 2, 3, 4, 5)])
    store = FakeSurfacedCallStore()
    md = FakeMarketData(
        signals={
            "ASTS": _prices("ASTS"),
            "DUD": _prices("DUD"),
            "XIC.TO": [
                Signal(
                    symbol="XIC.TO",
                    timestamp=NOW,
                    price=42.0,
                    volume=1.0,
                    open_=42.0,
                    high=42.0,
                    low=42.0,
                )
            ],
            "QQQ": _prices("QQQ"),
        },
        ticker_info={"ASTS": {"marketCap": 3e9}, "DUD": {"marketCap": 5e8}},
    )
    uc = OpportunityScanUseCase(
        universe_provider=FakeUniverseProvider(
            [UniverseEntry("ASTS", "space"), UniverseEntry("DUD", "space")]
        ),
        conviction_provider=_conviction("ASTS"),
        buzz_discovery=buzz,
        market_data=md,
        store=store,
        cmin=6.0,
        dmin=6.0,
        benchmark_ticker="XIC.TO",
    )
    calls = uc.execute(NOW)
    assert [c.ticker for c in calls] == ["ASTS"]
    assert calls[0].spy_at_surface == 42.0


def test_cap_tier_uses_marketcap_for_large():
    from tests.fakes.fake_attention_series import FakeAttentionSeries

    store = FakeSurfacedCallStore()
    uc = OpportunityScanUseCase(
        universe_provider=FakeUniverseProvider([UniverseEntry("META", "ai")]),
        conviction_provider=lambda t, now: (3.0, {"smart_money": 3.0}),
        buzz_discovery=FakeBuzzDiscovery([]),
        market_data=FakeMarketData(
            signals={"META": [], "SPY": [], "QQQ": []},
            ticker_info={"META": {"market_cap": 1.5e12}},
        ),
        store=store,
        attention_provider=FakeAttentionSeries([]),
        cmin=99.0,
        dmin=99.0,  # force abstain; we only inspect the logged candidate
    )
    uc.execute(NOW)
    assert store.candidates[0]["cap_tier"] == "large"
