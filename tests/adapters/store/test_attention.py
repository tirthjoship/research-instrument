"""Tests for AttentionMixin."""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from adapters.data.sqlite_store import SQLiteStore
from domain.models import AttentionPoint


def test_attention_series_roundtrip(tmp_path: pytest.TempPathFactory) -> None:
    store = SQLiteStore(str(tmp_path / "t.db"))  # type: ignore[arg-type]
    pts = [
        AttentionPoint("ASTS", datetime(2026, 6, 1), 10.0, "google_trends"),
        AttentionPoint("ASTS", datetime(2026, 6, 2), 80.0, "wikipedia"),
    ]
    store.save_attention_points(pts)
    got = store.get_attention_series("ASTS", datetime(2026, 5, 1), datetime(2026, 7, 1))
    assert len(got) == 2


def test_attention_series_dedupe(tmp_path: pytest.TempPathFactory) -> None:
    store = SQLiteStore(str(tmp_path / "t.db"))  # type: ignore[arg-type]
    p = AttentionPoint("ASTS", datetime(2026, 6, 1), 10.0, "google_trends")
    store.save_attention_points([p])
    store.save_attention_points([p])  # re-run, must not duplicate
    got = store.get_attention_series("ASTS", datetime(2026, 5, 1), datetime(2026, 7, 1))
    assert len(got) == 1


def test_attention_series_handles_aware_query(tmp_path: pytest.TempPathFactory) -> None:
    store = SQLiteStore(db_path=str(tmp_path / "t.db"))  # type: ignore[arg-type]
    # stored naive
    store.save_attention_points(
        [AttentionPoint("ASTS", datetime(2026, 6, 1), 10.0, "google_trends")]
    )
    # queried with aware bounds — must still find the row
    got = store.get_attention_series(
        "ASTS",
        datetime(2026, 5, 1, tzinfo=timezone.utc),
        datetime(2026, 7, 1, tzinfo=timezone.utc),
    )
    assert len(got) == 1


def test_attention_series_dedupe_across_naive_and_aware(
    tmp_path: pytest.TempPathFactory,
) -> None:
    store = SQLiteStore(db_path=str(tmp_path / "t.db"))  # type: ignore[arg-type]
    store.save_attention_points(
        [AttentionPoint("ASTS", datetime(2026, 6, 1), 10.0, "google_trends")]
    )
    store.save_attention_points(
        [
            AttentionPoint(
                "ASTS",
                datetime(2026, 6, 1, tzinfo=timezone.utc),
                10.0,
                "google_trends",
            )
        ]
    )
    got = store.get_attention_series("ASTS", datetime(2026, 5, 1), datetime(2026, 7, 1))
    assert len(got) == 1
