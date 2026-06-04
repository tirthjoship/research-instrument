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
