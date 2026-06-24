"""Tests for adapters.data.corroboration_gate_log — JSONL read/write/dedup."""

from __future__ import annotations

from datetime import date
from pathlib import Path
from typing import Literal

import pytest

from domain.corroboration_gate import GateResult, GateSample

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _sample(ticker: str = "AAPL", snap: str = "2026-01-01") -> GateSample:
    return GateSample(
        ticker=ticker,
        snapshot_date=date.fromisoformat(snap),
        resolved_at=date(2026, 1, 22),
        excess_21d=0.02,
        excess_63d=0.04,
        beat_spy_21d=True,
    )


def _result(verdict: str = "PENDING") -> GateResult:
    v: Literal["PENDING", "PASS", "FAIL"] = verdict  # type: ignore[assignment]
    return GateResult(
        n_resolved=10,
        mean_excess_21d=0.015,
        ci_lower=-0.005,
        ci_upper=0.035,
        hit_rate_21d=0.6,
        mean_excess_63d=0.02,
        verdict=v,
        evaluated_at=date(2026, 1, 22),
    )


# ---------------------------------------------------------------------------
# load_samples — missing file
# ---------------------------------------------------------------------------


def test_load_samples_missing_file_returns_empty(tmp_path: Path) -> None:
    from adapters.data.corroboration_gate_log import load_samples

    assert load_samples(tmp_path / "missing.jsonl") == []


# ---------------------------------------------------------------------------
# append_samples / load_samples — basic round-trip
# ---------------------------------------------------------------------------


def test_append_samples_returns_count_written(tmp_path: Path) -> None:
    from adapters.data.corroboration_gate_log import append_samples

    p = tmp_path / "samples.jsonl"
    n = append_samples(
        [_sample("AAPL", "2026-01-01"), _sample("MSFT", "2026-01-01")], p
    )
    assert n == 2


def test_load_samples_returns_all_written(tmp_path: Path) -> None:
    from adapters.data.corroboration_gate_log import append_samples, load_samples

    p = tmp_path / "samples.jsonl"
    append_samples([_sample("AAPL", "2026-01-01"), _sample("MSFT", "2026-01-01")], p)
    assert len(load_samples(p)) == 2


def test_append_samples_same_ticker_different_dates_both_written(
    tmp_path: Path,
) -> None:
    from adapters.data.corroboration_gate_log import append_samples, load_samples

    p = tmp_path / "samples.jsonl"
    n = append_samples(
        [_sample("AAPL", "2026-01-01"), _sample("AAPL", "2026-01-08")], p
    )
    assert n == 2
    assert len(load_samples(p)) == 2


# ---------------------------------------------------------------------------
# Dedup behaviour
# ---------------------------------------------------------------------------


def test_append_samples_dedup_skips_existing(tmp_path: Path) -> None:
    from adapters.data.corroboration_gate_log import append_samples, load_samples

    p = tmp_path / "samples.jsonl"
    # First call — writes 1
    n1 = append_samples([_sample("AAPL", "2026-01-01")], p)
    assert n1 == 1
    # Second call with same key — should skip
    n2 = append_samples([_sample("AAPL", "2026-01-01")], p)
    assert n2 == 0
    # Only 1 record total
    assert len(load_samples(p)) == 1


def test_append_samples_dedup_within_single_batch(tmp_path: Path) -> None:
    from adapters.data.corroboration_gate_log import append_samples, load_samples

    p = tmp_path / "samples.jsonl"
    # Two identical samples in one batch — only 1 should land
    n = append_samples(
        [_sample("AAPL", "2026-01-01"), _sample("AAPL", "2026-01-01")], p
    )
    assert n == 1
    assert len(load_samples(p)) == 1


def test_append_samples_partial_dedup(tmp_path: Path) -> None:
    from adapters.data.corroboration_gate_log import append_samples, load_samples

    p = tmp_path / "samples.jsonl"
    append_samples([_sample("AAPL", "2026-01-01")], p)
    # AAPL 01-01 already exists; MSFT 01-01 is new → only 1 written
    n = append_samples(
        [_sample("AAPL", "2026-01-01"), _sample("MSFT", "2026-01-01")], p
    )
    assert n == 1
    assert len(load_samples(p)) == 2


# ---------------------------------------------------------------------------
# excess_63d=None round-trip
# ---------------------------------------------------------------------------


def test_load_samples_excess_63d_none_roundtrip(tmp_path: Path) -> None:
    from adapters.data.corroboration_gate_log import append_samples, load_samples

    p = tmp_path / "samples.jsonl"
    s = GateSample(
        ticker="NVDA",
        snapshot_date=date(2026, 1, 1),
        resolved_at=date(2026, 1, 22),
        excess_21d=0.01,
        excess_63d=None,
        beat_spy_21d=False,
    )
    append_samples([s], p)
    loaded = load_samples(p)
    assert loaded[0].excess_63d is None


# ---------------------------------------------------------------------------
# append_result / load_latest_result
# ---------------------------------------------------------------------------


def test_load_latest_result_missing_file_returns_none(tmp_path: Path) -> None:
    from adapters.data.corroboration_gate_log import load_latest_result

    assert load_latest_result(tmp_path / "missing.jsonl") is None


def test_append_and_load_latest_result_roundtrip(tmp_path: Path) -> None:
    from adapters.data.corroboration_gate_log import append_result, load_latest_result

    p = tmp_path / "gate_log.jsonl"
    r = _result("PASS")
    append_result(r, p)
    loaded = load_latest_result(p)
    assert loaded is not None
    assert loaded.verdict == "PASS"
    assert loaded.n_resolved == 10
    assert loaded.mean_excess_21d == pytest.approx(0.015)
    assert loaded.evaluated_at == date(2026, 1, 22)


def test_load_latest_result_returns_last_appended(tmp_path: Path) -> None:
    from adapters.data.corroboration_gate_log import append_result, load_latest_result

    p = tmp_path / "gate_log.jsonl"
    append_result(_result("PENDING"), p)
    append_result(_result("PASS"), p)
    append_result(_result("FAIL"), p)
    loaded = load_latest_result(p)
    assert loaded is not None
    assert loaded.verdict == "FAIL"


def test_load_latest_result_mean_excess_63d_none_roundtrip(tmp_path: Path) -> None:
    from adapters.data.corroboration_gate_log import append_result, load_latest_result

    p = tmp_path / "gate_log.jsonl"
    r = GateResult(
        n_resolved=5,
        mean_excess_21d=0.01,
        ci_lower=-0.01,
        ci_upper=0.03,
        hit_rate_21d=0.5,
        mean_excess_63d=None,
        verdict="PENDING",
        evaluated_at=date(2026, 1, 22),
    )
    append_result(r, p)
    loaded = load_latest_result(p)
    assert loaded is not None
    assert loaded.mean_excess_63d is None


def test_load_latest_result_empty_file_returns_none(tmp_path: Path) -> None:
    from adapters.data.corroboration_gate_log import load_latest_result

    p = tmp_path / "gate_log.jsonl"
    p.touch()
    assert load_latest_result(p) is None


# ---------------------------------------------------------------------------
# Parent directory creation
# ---------------------------------------------------------------------------


def test_append_samples_creates_parent_dirs(tmp_path: Path) -> None:
    from adapters.data.corroboration_gate_log import append_samples

    nested = tmp_path / "a" / "b" / "samples.jsonl"
    n = append_samples([_sample()], nested)
    assert n == 1
    assert nested.exists()


def test_append_result_creates_parent_dirs(tmp_path: Path) -> None:
    from adapters.data.corroboration_gate_log import append_result

    nested = tmp_path / "x" / "y" / "gate_log.jsonl"
    append_result(_result(), nested)
    assert nested.exists()
