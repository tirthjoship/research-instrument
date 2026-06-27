import sqlite3
from datetime import date

from adapters.data.corroboration_store import CorroborationStore
from domain.corroboration_models import HarvestedClaim, Stance


def test_save_and_load_run_roundtrips() -> None:
    conn = sqlite3.connect(":memory:")
    store = CorroborationStore(conn)
    store.init_schema()
    claim = HarvestedClaim(
        "A",
        "NVDA",
        Stance.BULLISH,
        "why",
        "https://u",
        date(2026, 6, 18),
        True,
        0.7,
    )
    run_id = store.save_run(date(2026, 6, 20), [claim])
    loaded = store.load_run(run_id)
    assert loaded[0].ticker == "NVDA" and loaded[0].verified is True
