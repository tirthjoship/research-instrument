from datetime import date

from application.calibration_readiness import (
    as_of_spread,
    freshness,
    resolvable_split,
    spread_of_as_ofs,
)


def _row(verdict: str, as_of: str) -> dict[str, object]:
    return {"ticker": "X", "verdict": verdict, "price": 1.0, "as_of": as_of}


def test_spread_empty() -> None:
    s = spread_of_as_ofs([])
    assert s == {
        "distinct_dates": 0,
        "span_days": 0,
        "min_date": None,
        "max_date": None,
    }


def test_spread_single_date_dedupes_timestamps() -> None:
    s = spread_of_as_ofs(["2026-06-08T09:00:00+00:00", "2026-06-08T17:30:00+00:00"])
    assert s["distinct_dates"] == 1
    assert s["span_days"] == 0
    assert s["min_date"] == "2026-06-08"


def test_spread_multi_date_span() -> None:
    s = spread_of_as_ofs(["2026-06-08T09:00:00+00:00", "2026-06-18T09:00:00+00:00"])
    assert s["distinct_dates"] == 2
    assert s["span_days"] == 10
    assert s["max_date"] == "2026-06-18"


def test_as_of_spread_reads_rows() -> None:
    rows = [
        _row("REDUCE", "2026-06-08T09:00:00+00:00"),
        _row("REDUCE", "2026-06-13T09:00:00+00:00"),
    ]
    s = as_of_spread(rows)
    assert s["distinct_dates"] == 2 and s["span_days"] == 5


def test_resolvable_split_counts_reduce_only_past_horizon() -> None:
    rows = [
        _row("REDUCE", "2026-05-01T09:00:00+00:00"),  # old -> resolvable
        _row("REDUCE", "2026-06-08T09:00:00+00:00"),  # recent -> pending
        _row("TRIM", "2026-05-01T09:00:00+00:00"),  # not REDUCE -> ignored
    ]
    out = resolvable_split(rows, today=date(2026, 6, 9), horizon_days=21)
    assert out == {"resolvable": 1, "pending": 1}


def test_resolvable_split_boundary_exactly_horizon_is_resolvable() -> None:
    rows = [_row("REDUCE", "2026-05-19T00:00:00+00:00")]  # +21d = 2026-06-09
    out = resolvable_split(rows, today=date(2026, 6, 9), horizon_days=21)
    assert out == {"resolvable": 1, "pending": 0}


def test_freshness_days_since_last() -> None:
    rows = [
        _row("HOLD", "2026-06-04T09:00:00+00:00"),
        _row("REDUCE", "2026-06-08T09:00:00+00:00"),
    ]
    assert freshness(rows, today=date(2026, 6, 9)) == 1


def test_freshness_none_when_empty() -> None:
    assert freshness([], today=date(2026, 6, 9)) is None
