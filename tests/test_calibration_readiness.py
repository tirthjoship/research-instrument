from datetime import date

from application.calibration_readiness import (
    as_of_spread,
    diversity_label,
    freshness,
    readiness,
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


def _reduce_on(dates: list[str]) -> list[dict[str, object]]:
    return [_row("REDUCE", f"{d}T09:00:00+00:00") for d in dates]


def test_readiness_single_date_is_thin_even_with_many_flags() -> None:
    rows = _reduce_on(["2026-06-08"] * 40)  # n big, but one date
    rep = readiness(
        rows, today=date(2026, 6, 9), horizon_days=21, gate_date=date(2026, 7, 15)
    )
    assert rep.verdict == "THIN"
    assert any("distinct_dates" in s for s in rep.shortfalls)


def test_readiness_diverse_and_enough_is_ready() -> None:
    # 30 flags across 3 dates spanning 14 days, all resolvable by the gate.
    dates = ["2026-06-09"] * 10 + ["2026-06-16"] * 10 + ["2026-06-23"] * 10
    rows = _reduce_on(dates)
    rep = readiness(
        rows, today=date(2026, 7, 14), horizon_days=21, gate_date=date(2026, 7, 15)
    )
    assert rep.verdict == "READY"
    assert rep.shortfalls == ()
    assert rep.projected_n_at_gate == 30
    assert rep.distinct_reduce_dates == 3


def test_readiness_projection_excludes_flags_resolving_after_gate() -> None:
    # logged too late to resolve by the gate (as_of + 21d > gate_date)
    rows = _reduce_on(["2026-07-10"] * 30)
    rep = readiness(
        rows, today=date(2026, 7, 11), horizon_days=21, gate_date=date(2026, 7, 15)
    )
    assert rep.projected_n_at_gate == 0
    assert rep.verdict == "THIN"


def _as_ofs(dates: list[str]) -> list[str]:
    return [f"{d}T09:00:00+00:00" for d in dates]


def test_guard_confounded_high_downrate_is_thin_not_proceed() -> None:
    # one date, n>=30, down_rate passes, brier passes -> STILL thin (symmetric)
    as_ofs = _as_ofs(["2026-06-08"] * 40)
    assert (
        diversity_label(as_ofs, down_rate=0.70, brier=0.30) == "INCONCLUSIVE_THIN_DATES"
    )


def test_guard_confounded_low_downrate_is_thin_not_kill() -> None:
    as_ofs = _as_ofs(["2026-06-08"] * 40)
    assert (
        diversity_label(as_ofs, down_rate=0.20, brier=0.60) == "INCONCLUSIVE_THIN_DATES"
    )


def test_guard_diverse_passing_thresholds_is_proceed() -> None:
    as_ofs = _as_ofs(["2026-06-09"] * 14 + ["2026-06-16"] * 14 + ["2026-06-23"] * 14)
    assert diversity_label(as_ofs, down_rate=0.60, brier=0.40) == "PROCEED"


def test_guard_diverse_failing_thresholds_is_kill() -> None:
    as_ofs = _as_ofs(["2026-06-09"] * 14 + ["2026-06-16"] * 14 + ["2026-06-23"] * 14)
    assert diversity_label(as_ofs, down_rate=0.40, brier=0.60) == "KILL"


def test_guard_thin_n_is_thin() -> None:
    as_ofs = _as_ofs(["2026-06-09", "2026-06-16", "2026-06-23"])  # diverse but n=3
    assert (
        diversity_label(as_ofs, down_rate=0.99, brier=0.01) == "INCONCLUSIVE_THIN_DATES"
    )
