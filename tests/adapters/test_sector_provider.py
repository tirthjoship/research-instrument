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


def test_unknown_not_persisted_to_disk(tmp_path):
    """Unknown sector must NOT be written to the JSON cache on disk."""
    cache = tmp_path / "sector_map.json"
    p = SectorProvider(cache_path=str(cache), fetcher=lambda t: None)
    p.sector("ZZZZ")
    # Either the file was never created, or it exists but does not contain "ZZZZ"/"Unknown"
    if cache.exists():
        import json

        data = json.loads(cache.read_text())
        assert "ZZZZ" not in data, "Unknown ticker must not be persisted to disk"
        assert (
            "Unknown" not in data.values()
        ), "Unknown value must not be persisted to disk"


def test_unknown_cached_in_memory_no_refetch(tmp_path):
    """Unknown sector is held in the in-memory cache so the fetcher is called only once."""
    cache = tmp_path / "sector_map.json"
    calls: list[str] = []

    def counting_fetcher(t: str) -> str | None:
        calls.append(t)
        return None

    p = SectorProvider(cache_path=str(cache), fetcher=counting_fetcher)
    result1 = p.sector("ZZZZ")
    result2 = p.sector("ZZZZ")
    assert result1 == "Unknown"
    assert result2 == "Unknown"
    assert calls == [
        "ZZZZ"
    ], "Fetcher must be called exactly once; in-memory cache holds Unknown"


def test_real_sector_still_persisted(tmp_path):
    """A successfully resolved sector must still be written to the disk cache."""
    cache = tmp_path / "sector_map.json"

    def fake_fetch(t: str) -> str | None:
        return {"NVDA": "Information Technology"}.get(t)

    p = SectorProvider(cache_path=str(cache), fetcher=fake_fetch)
    p.sector("NVDA")
    assert cache.exists(), "Cache file must be created for a real sector"
    import json

    data = json.loads(cache.read_text())
    assert data.get("NVDA") == "Information Technology"
