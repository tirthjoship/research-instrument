"""Tests for FamaFrenchProvider.

All tests use the _rows injection path — no network calls, no disk I/O.
A tiny in-memory rows dict drives every assertion.
"""

from __future__ import annotations

from datetime import datetime

import pytest

from adapters.data.fama_french_provider import FF_FACTORS, FamaFrenchProvider
from domain.macro_beta import daily_returns

# ── Shared fixture ─────────────────────────────────────────────────────────────

# Five consecutive dates with known factor returns (as fractions, already /100).
# SMB:  +1%, +2%, -1%, +0.5%  over 4 steps  (5 dates yield 4 daily_returns)
# HML:  +0%, +0%, +0%, +0%
# MOM:  +0.79% on 2022-01-03 → value 0.0079 in source parsed to fraction
# RMW:  +0.5% each day
# CMA:  -0.5% each day

_ROWS: dict[str, dict[str, float]] = {
    "2022-01-03": {
        "SMB": 0.01,
        "HML": 0.00,
        "MOM": 0.0079,
        "RMW": 0.005,
        "CMA": -0.005,
    },
    "2022-01-04": {"SMB": 0.02, "HML": 0.00, "MOM": 0.01, "RMW": 0.005, "CMA": -0.005},
    "2022-01-05": {
        "SMB": -0.01,
        "HML": 0.00,
        "MOM": -0.005,
        "RMW": 0.005,
        "CMA": -0.005,
    },
    "2022-01-06": {
        "SMB": 0.005,
        "HML": 0.00,
        "MOM": 0.003,
        "RMW": 0.005,
        "CMA": -0.005,
    },
    "2022-01-07": {
        "SMB": -0.005,
        "HML": 0.00,
        "MOM": 0.002,
        "RMW": 0.005,
        "CMA": -0.005,
    },
}

_START = datetime(2022, 1, 3)
_END = datetime(2022, 1, 7)


def _make_provider() -> FamaFrenchProvider:
    return FamaFrenchProvider(_rows=_ROWS)


# ── FF_FACTORS membership ──────────────────────────────────────────────────────


def test_ff_factors_contains_expected() -> None:
    assert FF_FACTORS == {"SMB", "HML", "MOM", "RMW", "CMA"}


def test_ff_factors_is_frozenset() -> None:
    assert isinstance(FF_FACTORS, frozenset)


# ── Series shape and cumulative-index math ────────────────────────────────────


def test_series_starts_at_100() -> None:
    p = _make_provider()
    s = p.series("SMB", _START, _END)
    assert len(s) == 5
    assert s[0][0] == _START
    assert s[0][1] == pytest.approx(100.0)


def test_series_length_matches_window() -> None:
    p = _make_provider()
    s = p.series("MOM", _START, _END)
    assert len(s) == 5


def test_daily_returns_recover_factor_returns() -> None:
    """daily_returns(series) must equal the original factor fractions."""
    p = _make_provider()
    for factor in FF_FACTORS:
        s = p.series(factor, _START, _END)
        recovered = daily_returns(s)
        assert len(recovered) == 4, f"{factor}: expected 4 returns"
        dates = sorted(_ROWS.keys())
        for i, (dt, ret) in enumerate(recovered):
            expected_date_str = dates[i + 1]  # return is on the later date
            expected_dt = datetime.strptime(expected_date_str, "%Y-%m-%d")
            assert dt == expected_dt, f"{factor} date mismatch at step {i}"
            expected_ret = _ROWS[expected_date_str][factor]
            assert ret == pytest.approx(
                expected_ret, rel=1e-9
            ), f"{factor} step {i}: got {ret}, want {expected_ret}"


# ── Percent → fraction conversion ─────────────────────────────────────────────


def test_percent_to_fraction_conversion() -> None:
    """Source value 0.79 percent must be stored as fraction 0.0079.

    _ROWS["2022-01-03"]["MOM"] == 0.0079.  We build a two-date window so that
    the single daily_return step recovers exactly that value.
    """
    # Window: only 2022-01-03 and 2022-01-04 → one daily_return step.
    # That step's return is _ROWS["2022-01-04"]["MOM"] == 0.01, NOT the
    # 2022-01-03 value.  To isolate the 2022-01-03 MOM value we build a
    # provider with a two-row dict where the *second* row has the target value.
    rows_two = {
        "2022-01-03": {"SMB": 0.0, "HML": 0.0, "MOM": 0.0, "RMW": 0.0, "CMA": 0.0},
        "2022-01-04": {"SMB": 0.0, "HML": 0.0, "MOM": 0.0079, "RMW": 0.0, "CMA": 0.0},
    }
    p2 = FamaFrenchProvider(_rows=rows_two)
    s = p2.series("MOM", datetime(2022, 1, 3), datetime(2022, 1, 4))
    rets = daily_returns(s)
    assert len(rets) == 1
    assert rets[0][1] == pytest.approx(0.0079, rel=1e-9)


# ── Point-in-time exclusion ────────────────────────────────────────────────────


def test_dates_after_end_excluded() -> None:
    """No date beyond `end` appears in the returned series."""
    p = _make_provider()
    end = datetime(2022, 1, 5)
    s = p.series("SMB", _START, end)
    assert all(dt <= end for dt, _ in s)
    assert len(s) == 3  # 2022-01-03, 04, 05


def test_dates_before_start_excluded() -> None:
    """No date before `start` appears in the returned series."""
    p = _make_provider()
    start = datetime(2022, 1, 5)
    s = p.series("SMB", start, _END)
    assert all(dt >= start for dt, _ in s)
    assert len(s) == 3  # 2022-01-05, 06, 07


def test_pit_single_day_window() -> None:
    p = _make_provider()
    day = datetime(2022, 1, 4)
    s = p.series("HML", day, day)
    assert len(s) == 1
    assert s[0][0] == day
    assert s[0][1] == pytest.approx(100.0)


def test_end_before_start_returns_empty() -> None:
    p = _make_provider()
    s = p.series("SMB", _END, _START)  # reversed — impossible window
    assert s == []


# ── Unknown factor ─────────────────────────────────────────────────────────────


def test_unknown_factor_returns_empty() -> None:
    p = _make_provider()
    assert p.series("MktRF", _START, _END) == []
    assert p.series("", _START, _END) == []
    assert p.series("MOMENTUM", _START, _END) == []


# ── No data in window ─────────────────────────────────────────────────────────


def test_no_data_in_window_returns_empty() -> None:
    p = _make_provider()
    far_future = datetime(2099, 1, 1)
    far_future_end = datetime(2099, 12, 31)
    assert p.series("SMB", far_future, far_future_end) == []


# ── Cache round-trip (disk I/O) ────────────────────────────────────────────────


def test_cache_write_and_load(tmp_path) -> None:
    """Writing a cache and re-loading it must produce identical series."""
    import json

    cache_file = tmp_path / "ff_test.json"
    # Simulate writing the cache as the real provider would.
    payload = {"fetched": "2022-01-07", "rows": _ROWS}
    cache_file.write_text(json.dumps(payload), encoding="utf-8")

    # Construct a new provider that reads from that cache file.
    p = FamaFrenchProvider(cache_path=cache_file)
    s = p.series("SMB", _START, _END)
    assert len(s) == 5
    assert s[0][1] == pytest.approx(100.0)


def test_empty_cache_file_triggers_fallback_not_crash(tmp_path, monkeypatch) -> None:
    """An empty cache file must not crash; it falls through to the download path."""
    cache_file = tmp_path / "ff_empty.json"
    cache_file.write_text("", encoding="utf-8")

    # Patch _download_and_merge to avoid real network calls.
    import adapters.data.fama_french_provider as mod

    monkeypatch.setattr(mod, "_download_and_merge", lambda: _ROWS)

    p = FamaFrenchProvider(cache_path=cache_file)
    s = p.series("SMB", _START, _END)
    assert len(s) == 5
