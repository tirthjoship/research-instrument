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
