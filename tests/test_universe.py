# tests/test_universe.py
from datetime import datetime, timezone

from domain.ports import SurfacedCallStorePort, UniverseProviderPort
from domain.universe import UniverseEntry


def test_universe_entry():
    e = UniverseEntry(ticker="ASTS", theme="space")
    assert e.ticker == "ASTS" and e.theme == "space"


def test_ports_are_runtime_checkable():
    class P:
        def get_universe(self, now: datetime) -> list[UniverseEntry]:
            return []

    assert isinstance(P(), UniverseProviderPort)


def test_surfaced_call_store_port_is_runtime_checkable():
    now = datetime(2026, 1, 1, tzinfo=timezone.utc)

    class S:
        def save_call(self, call):
            pass

        def get_call(self, call_id: str):
            return None

        def get_all_calls(self):
            return []

        def get_due_calls(self, now: datetime):
            return []

        def save_outcome(self, outcome):
            pass

        def get_outcomes(self):
            return []

    assert isinstance(S(), SurfacedCallStorePort)
    assert now.year == 2026  # use the import
