"""SnapshotScreenReader — the .run() interface EvidenceScreenUseCase exposes,
but backed by a published screen_<date>.json snapshot instead of a live
~512-ticker scan. Item 5 of the Cloud deploy scaling design: weekly-brief
reads this instead of re-scanning the universe on every visitor click."""

from __future__ import annotations

import json

from application.snapshot_screen import SnapshotScreenReader
from domain.screen_models import ScreenLabel


def _write_screen(tmp_path, as_of: str) -> None:
    payload = {
        "as_of": as_of,
        "universe_size": 512,
        "top_n": 10,
        "regime": "NEUTRAL",
        "abstained": False,
        "diagnostics": {
            "scanned": 512,
            "had_history": 480,
            "above_trend": 200,
            "cleared": 50,
        },
        "candidates": [
            {
                "ticker": "AAPL",
                "composite": 0.82,
                "trend_health": 0.5,
                "label": "RESEARCH_ONLY",
                "why": "strong momentum",
                "factor_scores": [
                    {
                        "name": "momentum",
                        "value": 1.2,
                        "percentile": 0.9,
                        "contribution": 0.3,
                    }
                ],
            }
        ],
    }
    (tmp_path / f"screen_{as_of}.json").write_text(json.dumps(payload))


def test_run_reads_latest_snapshot_not_live_scan(tmp_path) -> None:
    _write_screen(tmp_path, "2026-07-14")
    reader = SnapshotScreenReader(str(tmp_path))

    result = reader.run(universe=["AAPL", "MSFT"], as_of="2026-07-15", top_n=10)

    assert result.as_of == "2026-07-14"  # snapshot's own as_of, not the call's
    assert result.universe_size == 512
    assert len(result.candidates) == 1
    cand = result.candidates[0]
    assert cand.ticker == "AAPL"
    assert cand.composite == 0.82
    assert cand.label is ScreenLabel.RESEARCH_ONLY
    assert cand.factor_scores[0].name == "momentum"
    assert cand.factor_scores[0].contribution == 0.3


def test_run_reconstructs_diagnostics(tmp_path) -> None:
    _write_screen(tmp_path, "2026-07-14")
    reader = SnapshotScreenReader(str(tmp_path))

    result = reader.run(universe=[], as_of="2026-07-15")

    assert result.diagnostics is not None
    assert result.diagnostics.scanned == 512
    assert result.diagnostics.cleared == 50


def test_run_with_no_snapshot_abstains_honestly(tmp_path) -> None:
    reader = SnapshotScreenReader(str(tmp_path))

    result = reader.run(universe=["AAPL"], as_of="2026-07-15")

    assert result.candidates == ()
    assert result.abstained is True
    assert result.universe_size == 0
