from adapters.data.sector_provider import SectorProvider


def test_uses_cache_then_fetcher(tmp_path):
    cache = tmp_path / "sector_map.json"
    calls = []

    def fake_fetch(t):
        calls.append(t)
        return {"NVDA": "Information Technology"}.get(t)

    p = SectorProvider(cache_path=str(cache), fetcher=fake_fetch)
    assert p.sector("NVDA") == "Information Technology"
    assert p.sector("NVDA") == "Information Technology"
    assert calls == ["NVDA"]


def test_unknown_is_data_gap(tmp_path):
    p = SectorProvider(cache_path=str(tmp_path / "m.json"), fetcher=lambda t: None)
    assert p.sector("ZZZZ") == "Unknown"
