"""Tests for application/case_cache.py — cited-case cache (D1).

TDD: tests written before implementation.
"""

from __future__ import annotations

import json
import os

from domain.case_models import CasePoint, CaseResult

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_result(
    favor: tuple[CasePoint, ...] = (),
    watch: tuple[CasePoint, ...] = (),
    data_gap: bool = False,
) -> CaseResult:
    return CaseResult(in_favor=favor, to_watch=watch, data_gap=data_gap)


def _point(text: str = "good signal", source: str = "reported") -> CasePoint:
    return CasePoint(text=text, source_tag=source)


# ---------------------------------------------------------------------------
# D1-a: serialize / deserialize round-trip
# ---------------------------------------------------------------------------


def test_serialize_empty_result_roundtrip() -> None:
    from application.case_cache import deserialize_case, serialize_case

    result = _make_result(data_gap=True)
    d = serialize_case(result)
    recovered = deserialize_case(d)
    assert recovered == result


def test_serialize_with_points_roundtrip() -> None:
    from application.case_cache import deserialize_case, serialize_case

    result = _make_result(
        favor=(
            _point("Revenue grew 12%", "reported"),
            _point("Analyst upgrades 3/5", "valuation"),
        ),
        watch=(_point("Debt/equity widened", "financials"),),
        data_gap=False,
    )
    d = serialize_case(result)
    recovered = deserialize_case(d)
    assert recovered == result


def test_serialize_produces_json_safe_dict() -> None:
    """serialize_case must return a plain dict that json.dumps can handle."""
    from application.case_cache import serialize_case

    result = _make_result(
        favor=(_point("fact", "src"),),
        watch=(_point("risk", "rag"),),
        data_gap=False,
    )
    d = serialize_case(result)
    # Must not raise:
    json.dumps(d)
    assert isinstance(d, dict)
    assert "in_favor" in d
    assert "to_watch" in d
    assert "data_gap" in d


def test_serialize_point_structure() -> None:
    from application.case_cache import serialize_case

    result = _make_result(favor=(_point("text1", "src1"),))
    d = serialize_case(result)
    assert d["in_favor"][0] == {"text": "text1", "source": "src1"}


# ---------------------------------------------------------------------------
# D1-b: write_case_cache / load_cached_case
# ---------------------------------------------------------------------------


def test_write_then_load_returns_same_result(tmp_path: object) -> None:
    from application.case_cache import load_cached_case, write_case_cache

    assert isinstance(tmp_path, os.PathLike)
    cache_path = str(tmp_path / "cited_cases.json")
    result = _make_result(
        favor=(_point("signal A"),),
        watch=(_point("risk B"),),
    )
    write_case_cache(cache_path, "2026-06-14", {"AAPL": result})
    loaded = load_cached_case(cache_path, "AAPL")
    assert loaded == result


def test_write_multiple_tickers_load_each(tmp_path: object) -> None:
    from application.case_cache import load_cached_case, write_case_cache

    assert isinstance(tmp_path, os.PathLike)
    cache_path = str(tmp_path / "cited_cases.json")
    r1 = _make_result(favor=(_point("r1"),))
    r2 = _make_result(watch=(_point("r2"),))
    write_case_cache(cache_path, "2026-06-14", {"MSFT": r1, "NVDA": r2})

    assert load_cached_case(cache_path, "MSFT") == r1
    assert load_cached_case(cache_path, "NVDA") == r2


def test_load_missing_ticker_returns_none(tmp_path: object) -> None:
    from application.case_cache import load_cached_case, write_case_cache

    assert isinstance(tmp_path, os.PathLike)
    cache_path = str(tmp_path / "cited_cases.json")
    write_case_cache(cache_path, "2026-06-14", {"AAPL": _make_result()})
    assert load_cached_case(cache_path, "TSLA") is None


def test_load_missing_file_returns_none(tmp_path: object) -> None:
    from application.case_cache import load_cached_case

    assert isinstance(tmp_path, os.PathLike)
    missing = str(tmp_path / "nonexistent.json")
    assert load_cached_case(missing, "AAPL") is None


def test_cache_file_has_as_of_field(tmp_path: object) -> None:
    from application.case_cache import write_case_cache

    assert isinstance(tmp_path, os.PathLike)
    cache_path = str(tmp_path / "cited_cases.json")
    write_case_cache(cache_path, "2026-06-14", {"AAPL": _make_result()})
    raw = json.loads(open(cache_path).read())
    assert raw["as_of"] == "2026-06-14"
    assert "cases" in raw


def test_write_creates_parent_dir(tmp_path: object) -> None:
    from application.case_cache import load_cached_case, write_case_cache

    assert isinstance(tmp_path, os.PathLike)
    nested = str(tmp_path / "deep" / "sub" / "cited_cases.json")
    write_case_cache(nested, "2026-06-14", {"AAPL": _make_result()})
    assert load_cached_case(nested, "AAPL") is not None
