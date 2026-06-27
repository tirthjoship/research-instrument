"""Tests for CandidatesMixin."""

from __future__ import annotations

import pytest

from adapters.data.sqlite_store import SQLiteStore


def test_scan_candidates_roundtrip(tmp_path: pytest.TempPathFactory) -> None:
    store = SQLiteStore(str(tmp_path / "t.db"))  # type: ignore[arg-type]
    store.save_scan_candidate(
        scan_date="2026-06-05",
        ticker="ASTS",
        conviction=6.4,
        divergence=7.1,
        sub_scores={"smart_money": 8.0, "event_signal": 6.0},
        surfaced=True,
        theme="space",
        cap_tier="mid",
    )
    rows = store.get_scan_candidates(scan_date="2026-06-05")
    assert len(rows) == 1
    assert rows[0]["ticker"] == "ASTS"
    assert rows[0]["surfaced"] == 1
    assert rows[0]["sub_scores"]["smart_money"] == 8.0
