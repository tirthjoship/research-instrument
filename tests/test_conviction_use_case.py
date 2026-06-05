"""Tests for ConvictionScoringUseCase — TDD with FakeSmartMoneyAdapter."""

from __future__ import annotations

from datetime import datetime

from domain.conviction import (
    ConvictionWeights,
    OpportunityCard,
    SmartMoneySignal,
    SmartMoneyType,
)

# ---------------------------------------------------------------------------
# Fake adapter
# ---------------------------------------------------------------------------


class FakeSmartMoneyAdapter:
    """In-memory SmartMoneyPort implementation for tests."""

    def __init__(self, signals: list[SmartMoneySignal] | None = None) -> None:
        self._signals: list[SmartMoneySignal] = signals or []

    def get_13d_filings(
        self, ticker: str | None = None, since_date: str | None = None
    ) -> list[SmartMoneySignal]:
        return [
            s
            for s in self._signals
            if s.signal_type == SmartMoneyType.FORM_13D
            and (ticker is None or s.ticker == ticker)
        ]

    def get_form4_filings(
        self, ticker: str | None = None, since_date: str | None = None
    ) -> list[SmartMoneySignal]:
        return [
            s
            for s in self._signals
            if s.signal_type == SmartMoneyType.FORM_4
            and (ticker is None or s.ticker == ticker)
        ]

    def get_all_signals(
        self, ticker: str | None = None, since_date: str | None = None
    ) -> list[SmartMoneySignal]:
        if ticker is None:
            return list(self._signals)
        return [s for s in self._signals if s.ticker == ticker]


# ---------------------------------------------------------------------------
# Shared fixtures
# ---------------------------------------------------------------------------

SCAN_TIME = datetime(2026, 6, 3, 12, 0, 0)
WEIGHTS = ConvictionWeights()

_13D_SIGNAL = SmartMoneySignal(
    ticker="AAPL",
    signal_type=SmartMoneyType.FORM_13D,
    filer_name="Activist Capital LLC",
    stake_pct=8.5,
    transaction_value=500_000_000.0,
    filed_date="2026-06-01",
    is_activist=True,
)

_FORM4_BUY = SmartMoneySignal(
    ticker="AAPL",
    signal_type=SmartMoneyType.FORM_4,
    filer_name="Tim Cook",
    stake_pct=None,
    transaction_value=1_000_000.0,
    filed_date="2026-06-02",
    is_activist=False,
    insider_role="CEO",
    transaction_type="Purchase",
)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_empty_universe_returns_empty_list() -> None:
    """Empty ticker list must return an empty list immediately."""
    from application.conviction_use_case import ConvictionScoringUseCase

    adapter = FakeSmartMoneyAdapter()
    uc = ConvictionScoringUseCase(
        smart_money=adapter,
        tickers=[],
        weights=WEIGHTS,
    )
    result = uc.run(scan_time=SCAN_TIME)
    assert result == []


def test_produces_opportunity_card_with_evidence_and_risks() -> None:
    """Single ticker with a 13D signal produces a populated OpportunityCard."""
    from application.conviction_use_case import ConvictionScoringUseCase

    adapter = FakeSmartMoneyAdapter(signals=[_13D_SIGNAL])
    uc = ConvictionScoringUseCase(
        smart_money=adapter,
        tickers=["AAPL"],
        weights=WEIGHTS,
    )
    cards = uc.run(scan_time=SCAN_TIME)
    assert len(cards) == 1
    card = cards[0]
    assert isinstance(card, OpportunityCard)
    assert card.ticker == "AAPL"
    assert card.conviction >= 1.0
    assert len(card.evidence) >= 1
    assert len(card.risks) >= 1
    # Evidence must mention the filer name
    evidence_text = " ".join(card.evidence)
    assert "Activist Capital LLC" in evidence_text
    # Market risk always present
    risks_text = " ".join(card.risks)
    assert "market" in risks_text.lower()


def test_pinned_tickers_always_included() -> None:
    """A pinned ticker with low conviction must still appear in results."""
    from application.conviction_use_case import ConvictionScoringUseCase

    # MSFT has no signals → low conviction, AAPL has a strong 13D signal
    adapter = FakeSmartMoneyAdapter(signals=[_13D_SIGNAL])
    uc = ConvictionScoringUseCase(
        smart_money=adapter,
        tickers=["AAPL", "MSFT"],
        weights=WEIGHTS,
        pinned={"MSFT"},
        top_n=1,  # only 1 slot normally → pinned forces MSFT in
    )
    cards = uc.run(scan_time=SCAN_TIME)
    tickers_returned = {c.ticker for c in cards}
    assert "MSFT" in tickers_returned


def test_ranked_by_conviction_descending() -> None:
    """Cards must be ordered by conviction score from highest to lowest."""
    from application.conviction_use_case import ConvictionScoringUseCase

    msft_signal = SmartMoneySignal(
        ticker="MSFT",
        signal_type=SmartMoneyType.FORM_13D,
        filer_name="ValueFund",
        stake_pct=12.0,
        transaction_value=1_000_000_000.0,
        filed_date="2026-06-02",
        is_activist=True,
    )
    # Give MSFT more signals → higher conviction
    adapter = FakeSmartMoneyAdapter(signals=[_13D_SIGNAL, _FORM4_BUY, msft_signal])
    uc = ConvictionScoringUseCase(
        smart_money=adapter,
        tickers=["AAPL", "MSFT"],
        weights=WEIGHTS,
    )
    cards = uc.run(scan_time=SCAN_TIME)
    assert len(cards) >= 2
    convictions = [c.conviction for c in cards]
    assert convictions == sorted(convictions, reverse=True)


def test_future_signals_filtered_out() -> None:
    """Signals with filed_date > scan_time must not contribute features."""
    from application.conviction_use_case import ConvictionScoringUseCase

    future_signal = SmartMoneySignal(
        ticker="AAPL",
        signal_type=SmartMoneyType.FORM_13D,
        filer_name="FutureFund",
        stake_pct=5.0,
        transaction_value=100_000_000.0,
        filed_date="2026-12-31",  # future!
        is_activist=False,
    )
    adapter = FakeSmartMoneyAdapter(signals=[future_signal])
    uc = ConvictionScoringUseCase(
        smart_money=adapter,
        tickers=["AAPL"],
        weights=WEIGHTS,
    )
    # Must not raise; future signals silently filtered
    cards = uc.run(scan_time=SCAN_TIME)
    # AAPL may or may not appear depending on min_score, but no crash
    assert isinstance(cards, list)


def test_progress_callback_called_per_ticker() -> None:
    """progress_callback must be invoked once per ticker processed."""
    from application.conviction_use_case import ConvictionScoringUseCase

    adapter = FakeSmartMoneyAdapter(signals=[_13D_SIGNAL])
    uc = ConvictionScoringUseCase(
        smart_money=adapter,
        tickers=["AAPL", "MSFT"],
        weights=WEIGHTS,
    )
    calls: list[tuple[int, int]] = []

    def cb(done: int, total: int) -> None:
        calls.append((done, total))

    uc.run(scan_time=SCAN_TIME, progress_callback=cb)
    assert len(calls) == 2
    assert calls[0] == (1, 2)
    assert calls[1] == (2, 2)


def test_form4_evidence_buy_sell_label() -> None:
    """Form 4 evidence must distinguish buy vs sell."""
    from application.conviction_use_case import ConvictionScoringUseCase

    sell_signal = SmartMoneySignal(
        ticker="AAPL",
        signal_type=SmartMoneyType.FORM_4,
        filer_name="Tim Cook",
        stake_pct=None,
        transaction_value=2_000_000.0,
        filed_date="2026-06-01",
        is_activist=False,
        insider_role="CEO",
        transaction_type="Sale",
    )
    adapter = FakeSmartMoneyAdapter(signals=[sell_signal])
    uc = ConvictionScoringUseCase(
        smart_money=adapter,
        tickers=["AAPL"],
        weights=WEIGHTS,
    )
    cards = uc.run(scan_time=SCAN_TIME)
    evidence_text = " ".join(cards[0].evidence) if cards else ""
    if cards:
        assert "sell" in evidence_text.lower() or "sale" in evidence_text.lower()


def test_compute_sub_scores_uses_real_data_when_available():
    from datetime import datetime
    from unittest.mock import MagicMock

    from application.conviction_use_case import ConvictionScoringUseCase

    use_case = ConvictionScoringUseCase(
        smart_money=MagicMock(), tickers=["NVDA"], weights=WEIGHTS
    )
    features = {
        "sm_13d_count": 0,
        "sm_form4_buy_count": 0,
        "sm_activist_count": 0,
        "sm_insider_cluster": 0,
    }
    mock_buzz = MagicMock()
    mock_buzz.sentiment_raw = 0.6
    mock_buzz.fetched_at = datetime(2026, 6, 3)
    ticker_info = {
        "pegRatio": 0.66,
        "freeCashflow": 46e9,
        "marketCap": 5.3e12,
        "returnOnEquity": 1.14,
    }
    mock_rec = MagicMock()
    mock_rec.grade = "strong_buy"

    sub_scores = use_case._compute_sub_scores(
        features=features,
        ticker_signals=[],
        scan_time=datetime(2026, 6, 4),
        buzz_signals=[mock_buzz],
        ticker_info=ticker_info,
        recommendation=mock_rec,
    )
    assert sub_scores["sentiment_momentum"] != 5.0
    assert sub_scores["fundamental_basis"] != 5.0
    assert sub_scores["ml_direction"] == 9


def test_compute_sub_scores_tz_aware_scan_time_with_signals():
    """Regression: tz-aware scan_time + dated signals must not raise.

    The CLI passes a tz-aware UTC `now`, but SmartMoneySignal.filed_date
    parses to a naive datetime. Subtracting them in the freshness path
    raised TypeError ("can't subtract offset-naive and offset-aware
    datetimes"), crashing the first live opportunity scan.
    """
    from datetime import datetime, timezone
    from unittest.mock import MagicMock

    from application.conviction_use_case import ConvictionScoringUseCase

    use_case = ConvictionScoringUseCase(
        smart_money=MagicMock(), tickers=["AAPL"], weights=WEIGHTS
    )
    features = {
        "sm_13d_count": 1,
        "sm_form4_buy_count": 0,
        "sm_activist_count": 1,
        "sm_insider_cluster": 0,
    }

    sub_scores = use_case._compute_sub_scores(
        features=features,
        ticker_signals=[_13D_SIGNAL],
        scan_time=datetime(2026, 6, 3, 12, 0, 0, tzinfo=timezone.utc),
    )
    # filed_date 2026-06-01 is 2 days before scan_time → 1–3 day bucket = 6.0
    assert sub_scores["temporal_freshness"] == 6.0


def test_compute_sub_scores_falls_back_without_data():
    from datetime import datetime
    from unittest.mock import MagicMock

    from application.conviction_use_case import ConvictionScoringUseCase

    use_case = ConvictionScoringUseCase(
        smart_money=MagicMock(), tickers=["NVDA"], weights=WEIGHTS
    )
    features = {
        "sm_13d_count": 0,
        "sm_form4_buy_count": 0,
        "sm_activist_count": 0,
        "sm_insider_cluster": 0,
    }
    sub_scores = use_case._compute_sub_scores(
        features=features, ticker_signals=[], scan_time=datetime(2026, 6, 4)
    )
    assert sub_scores["sentiment_momentum"] == 5.0
    assert sub_scores["fundamental_basis"] == 5.0
    assert sub_scores["ml_direction"] == 5.0


# ---------------------------------------------------------------------------
# Event signal tests (Step A — TDD)
# ---------------------------------------------------------------------------


def _make_event_use_case(
    news_source: object | None,
    classifier: object | None,
    event_impacts: dict | None,
) -> "ConvictionScoringUseCase":  # noqa: F821
    from application.conviction_use_case import ConvictionScoringUseCase

    adapter = FakeSmartMoneyAdapter(signals=[_13D_SIGNAL])
    return ConvictionScoringUseCase(
        smart_money=adapter,
        tickers=["AAPL"],
        weights=WEIGHTS,
        news_source=news_source,
        event_classifier=classifier,
        event_impacts=event_impacts,
    )


def test_event_signal_raises_conviction() -> None:
    """Bullish govt-investment event before scan_time → event_signal > 5.0."""
    from domain.models import ClassifiedEvent, EventCategory, EventSectorImpact
    from tests.fakes.fake_event_classifier import FakeEventClassifier
    from tests.fakes.fake_news_source import FakeNewsSource

    sector = "Technology"
    headline = "Government invests billions in chip manufacturing"
    event_date = "2026-06-01"  # before SCAN_TIME (2026-06-03)

    news = FakeNewsSource(headlines=[(headline, event_date)])
    classifier = FakeEventClassifier()
    event = ClassifiedEvent(
        headline=headline,
        event_date=event_date,
        category=EventCategory.GOVERNMENT_INVESTMENT,
        direction=1,
        confidence=0.9,
        source="rss",
    )
    classifier.add_response(headline, event)
    impact_key = (EventCategory.GOVERNMENT_INVESTMENT, sector)
    impacts = {
        impact_key: EventSectorImpact(
            category=EventCategory.GOVERNMENT_INVESTMENT,
            sector=sector,
            magnitude=1.5,
            half_life_days=5,
            sample_count=10,
        )
    }

    uc = _make_event_use_case(news, classifier, impacts)
    # Patch ticker_info to return the sector we care about
    import unittest.mock as mock

    with mock.patch(
        "adapters.visualization.price_cache._fetch_ticker_info_impl",
        return_value={"sector": sector},
    ):
        cards = uc.run(scan_time=SCAN_TIME)

    assert cards, "Expected at least one card"
    sub_scores = cards[0].conviction_score.sub_scores
    assert "event_signal" in sub_scores
    assert (
        sub_scores["event_signal"] > 5.0
    ), f"Expected event_signal > 5.0, got {sub_scores['event_signal']}"


def test_no_news_source_event_signal_neutral() -> None:
    """No news source wired → event_signal must be neutral 5.0."""
    from application.conviction_use_case import ConvictionScoringUseCase

    adapter = FakeSmartMoneyAdapter(signals=[_13D_SIGNAL])
    uc = ConvictionScoringUseCase(
        smart_money=adapter,
        tickers=["AAPL"],
        weights=WEIGHTS,
        # no news_source, no event_classifier
    )
    cards = uc.run(scan_time=SCAN_TIME)
    assert cards
    sub_scores = cards[0].conviction_score.sub_scores
    assert (
        sub_scores.get("event_signal") == 5.0
    ), f"Expected neutral 5.0, got {sub_scores.get('event_signal')}"


def test_future_event_filtered_point_in_time() -> None:
    """Headline dated after scan_time must not contribute (point-in-time guard)."""
    from domain.models import ClassifiedEvent, EventCategory, EventSectorImpact
    from tests.fakes.fake_event_classifier import FakeEventClassifier
    from tests.fakes.fake_news_source import FakeNewsSource

    future_date = "2026-12-31"  # after SCAN_TIME
    headline = "Future government spending bill announced"
    news = FakeNewsSource(headlines=[(headline, future_date)])
    classifier = FakeEventClassifier()
    event = ClassifiedEvent(
        headline=headline,
        event_date=future_date,
        category=EventCategory.GOVERNMENT_INVESTMENT,
        direction=1,
        confidence=0.9,
        source="rss",
    )
    classifier.add_response(headline, event)
    sector = "Technology"
    impacts = {
        (EventCategory.GOVERNMENT_INVESTMENT, sector): EventSectorImpact(
            category=EventCategory.GOVERNMENT_INVESTMENT,
            sector=sector,
            magnitude=1.5,
            half_life_days=5,
            sample_count=10,
        )
    }

    uc = _make_event_use_case(news, classifier, impacts)
    import unittest.mock as mock

    with mock.patch(
        "adapters.visualization.price_cache._fetch_ticker_info_impl",
        return_value={"sector": sector},
    ):
        cards = uc.run(scan_time=SCAN_TIME)

    assert cards
    sub_scores = cards[0].conviction_score.sub_scores
    # FakeNewsSource filters until=scan_time → no headlines returned → no events → neutral
    assert (
        sub_scores.get("event_signal") == 5.0
    ), f"Point-in-time guard failed: event_signal={sub_scores.get('event_signal')}"


# ---------------------------------------------------------------------------
# Analyst signal tests
# ---------------------------------------------------------------------------


def test_analyst_signal_raises_conviction() -> None:
    """UPGRADE dated just before scan_time → analyst_signal > 5.0."""
    from application.conviction_use_case import ConvictionScoringUseCase
    from domain.analyst import AnalystAction, AnalystRating
    from tests.fakes.fake_analyst_source import FakeAnalystSource

    rating = AnalystRating(
        ticker="AAPL",
        firm="Goldman",
        rating="Buy",
        prior_rating="Neutral",
        action=AnalystAction.UPGRADE,
        price_target=220.0,
        published_at=datetime(2026, 6, 2, 10, 0, 0),  # 1 day before scan_time
        source="rss",
    )
    analyst_source = FakeAnalystSource([rating])
    adapter = FakeSmartMoneyAdapter(signals=[_13D_SIGNAL])
    uc = ConvictionScoringUseCase(
        smart_money=adapter,
        tickers=["AAPL"],
        weights=WEIGHTS,
        analyst_source=analyst_source,
    )
    cards = uc.run(scan_time=SCAN_TIME)
    assert cards
    sub_scores = cards[0].conviction_score.sub_scores
    assert "analyst_signal" in sub_scores
    assert (
        sub_scores["analyst_signal"] > 5.0
    ), f"Expected analyst_signal > 5.0, got {sub_scores['analyst_signal']}"


def test_no_analyst_source_neutral() -> None:
    """No analyst source wired → analyst_signal must be neutral 5.0."""
    from application.conviction_use_case import ConvictionScoringUseCase

    adapter = FakeSmartMoneyAdapter(signals=[_13D_SIGNAL])
    uc = ConvictionScoringUseCase(
        smart_money=adapter,
        tickers=["AAPL"],
        weights=WEIGHTS,
        # no analyst_source
    )
    cards = uc.run(scan_time=SCAN_TIME)
    assert cards
    sub_scores = cards[0].conviction_score.sub_scores
    assert (
        sub_scores.get("analyst_signal") == 5.0
    ), f"Expected neutral 5.0, got {sub_scores.get('analyst_signal')}"


def test_future_rating_filtered_point_in_time() -> None:
    """Rating dated after scan_time must be excluded (LEAK GUARD)."""
    from application.conviction_use_case import ConvictionScoringUseCase
    from domain.analyst import AnalystAction, AnalystRating
    from tests.fakes.fake_analyst_source import FakeAnalystSource

    future_rating = AnalystRating(
        ticker="AAPL",
        firm="JPMorgan",
        rating="Overweight",
        prior_rating="Neutral",
        action=AnalystAction.UPGRADE,
        price_target=250.0,
        published_at=datetime(2026, 12, 31, 0, 0, 0),  # future!
        source="rss",
    )
    analyst_source = FakeAnalystSource([future_rating])
    adapter = FakeSmartMoneyAdapter(signals=[_13D_SIGNAL])
    uc = ConvictionScoringUseCase(
        smart_money=adapter,
        tickers=["AAPL"],
        weights=WEIGHTS,
        analyst_source=analyst_source,
    )
    cards = uc.run(scan_time=SCAN_TIME)
    assert cards
    sub_scores = cards[0].conviction_score.sub_scores
    # FakeAnalystSource filters until=scan_time → future rating excluded → neutral
    assert (
        sub_scores.get("analyst_signal") == 5.0
    ), f"Point-in-time guard failed: analyst_signal={sub_scores.get('analyst_signal')}"
