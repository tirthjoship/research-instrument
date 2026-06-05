# tests/test_hybrid_universe.py
from datetime import datetime, timezone
from pathlib import Path

import yaml

from adapters.data.hybrid_universe_provider import HybridUniverseProvider
from domain.models import BuzzSignal
from tests.fakes.fake_buzz_discovery import FakeBuzzDiscovery

NOW = datetime(2026, 6, 5, tzinfo=timezone.utc)


def test_themes_yaml_has_space_and_memory():
    data = yaml.safe_load(Path("config/universe/themes.yaml").read_text())
    themes = data["themes"]
    assert "ASTS" in themes["space"]
    assert "MU" in themes["memory_storage"]


def _buzz(ticker):
    return BuzzSignal(
        ticker=ticker,
        source="reddit",
        mention_count=1,
        sentiment_raw=0.5,
        scorer="keyword",
        fetched_at=NOW,
        article_hash=f"hash_{ticker}",
    )


def test_hybrid_merges_spine_and_discovery():
    prov = HybridUniverseProvider(
        themes_path="config/universe/themes.yaml",
        buzz_discovery=FakeBuzzDiscovery([_buzz("PLTR"), _buzz("ASTS")]),
    )
    uni = prov.get_universe(NOW)
    tickers = {e.ticker for e in uni}
    assert "ASTS" in tickers
    assert "PLTR" in tickers
    asts = next(e for e in uni if e.ticker == "ASTS")
    assert asts.theme == "space"
    pltr = next(e for e in uni if e.ticker == "PLTR")
    assert pltr.theme == "discovery"


def test_discovery_failure_falls_back_to_spine():
    class Boom:
        def scan_sources(self, now):
            raise RuntimeError("network down")

        def get_buzz_signals(self, **k):
            return []

    prov = HybridUniverseProvider("config/universe/themes.yaml", Boom())
    uni = prov.get_universe(NOW)
    assert any(e.ticker == "ASTS" for e in uni)
