import sqlite3
from datetime import date, timedelta

from adapters.data.corroboration_store import CorroborationStore
from application.corroboration_use_case import CorroborationUseCase
from domain.corroboration_models import HarvestedClaim, OurReadout, Stance, TrendHealth
from tests.fakes.corroboration_fakes import FakeHarvester, FakeVerifier


def _readout(ticker: str, as_of: date) -> OurReadout:
    return OurReadout(5.0, TrendHealth.HEALTHY, False, None)


def test_use_case_emits_candidates_and_persists() -> None:
    conn = sqlite3.connect(":memory:")
    store = CorroborationStore(conn)
    store.init_schema()
    uc = CorroborationUseCase(
        harvester=FakeHarvester(["NVDA"]),
        verifier=FakeVerifier(good_urls={"https://good/NVDA"}),
        readout_fn=_readout,
        held_tickers=set(),
        store=store,
    )
    result = uc.execute(date(2026, 6, 20))
    assert result.candidates and result.candidates[0].ticker == "NVDA"
    assert result.run_id is not None


class _FutureDatedHarvester:
    """Harvester that emits a claim published AFTER the as_of date."""

    def __init__(self, ticker: str, as_of: date) -> None:
        self._claim = HarvestedClaim(
            "src",
            ticker,
            Stance.BULLISH,
            "why",
            f"https://good/{ticker}",
            as_of + timedelta(days=3),
            True,
            0.6,
        )

    def harvest(self, as_of: date) -> list[HarvestedClaim]:
        return [self._claim]


def test_point_in_time_guard_drops_future_dated_claims() -> None:
    # Leakage guard (spec §9): a claim dated after as_of must never reach a tier.
    as_of = date(2026, 6, 20)
    conn = sqlite3.connect(":memory:")
    store = CorroborationStore(conn)
    store.init_schema()
    uc = CorroborationUseCase(
        harvester=_FutureDatedHarvester("NVDA", as_of),
        verifier=FakeVerifier(good_urls={"https://good/NVDA"}),
        readout_fn=_readout,
        held_tickers=set(),
        store=store,
    )
    result = uc.execute(as_of)
    assert result.candidates == []
