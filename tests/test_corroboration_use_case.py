import sqlite3
from datetime import date

from adapters.data.corroboration_store import CorroborationStore
from application.corroboration_use_case import CorroborationUseCase
from domain.corroboration_models import OurReadout, TrendHealth
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
