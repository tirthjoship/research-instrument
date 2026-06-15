"""TDD tests for ticker_factors_use_case — Task 2 (S5)."""

from __future__ import annotations

from typing import Any

import pytest

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

_FAKE_FACTOR_SCORES_SPG = [
    {"name": "momentum", "value": 0.22, "percentile": 0.59},
    {"name": "revision", "value": 1.1, "percentile": 0.88},
    {"name": "quality", "value": 1.5, "percentile": 0.95},
    {"name": "value", "value": 0.8, "percentile": 0.87},
    {"name": "lowvol", "value": None, "percentile": None},
]

_FAKE_FACTOR_SCORES_KLAC = [
    {"name": "momentum", "value": 0.9, "percentile": 0.81},
    {"name": "revision", "value": 0.3, "percentile": 0.55},
    {"name": "quality", "value": 1.8, "percentile": 0.97},
    {"name": "value", "value": -0.8, "percentile": 0.15},
    {"name": "lowvol", "value": None, "percentile": None},
]


@pytest.fixture()
def fake_screen_with_factors() -> dict[str, Any]:
    """Minimal fake screen dict with 2 candidates that have factor_scores."""
    return {
        "as_of": "2026-06-14",
        "candidates": [
            {
                "ticker": "SPG",
                "composite": 1.27,
                "factor_scores": _FAKE_FACTOR_SCORES_SPG,
            },
            {
                "ticker": "KLAC",
                "composite": 1.08,
                "factor_scores": _FAKE_FACTOR_SCORES_KLAC,
            },
        ],
    }


def _no_fetch(ticker: str) -> dict[str, float | None]:
    """fetch_fn that should never be called for in-screen tickers."""
    raise AssertionError(f"fetch_fn should not be called for in-screen ticker {ticker}")


def _fetch_raises(ticker: str) -> dict[str, float | None]:
    """fetch_fn that simulates a data failure (DATA-GAP)."""
    raise RuntimeError(f"No data available for {ticker}")


def _fake_fetch(ticker: str) -> dict[str, float | None]:
    """fetch_fn that returns plausible raw sub-scores for off-universe ticker."""
    # These are raw z-scores for ZZZZ — not in the cohort
    return {
        "momentum": 0.5,
        "revision": 0.7,
        "quality": 1.0,
        "value": -0.3,
        "lowvol": None,
    }


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_in_screen_ticker_reuses_stored_scores(
    fake_screen_with_factors: dict[str, Any],
) -> None:
    from application.ticker_factors_use_case import ticker_factor_scores

    fs = ticker_factor_scores(
        "SPG", screen=fake_screen_with_factors, fetch_fn=_no_fetch
    )
    # Should return the stored scores, containing the live factors
    names = {f["name"] for f in fs}
    assert names >= {"momentum", "value", "quality", "revision"}
    # Stored percentiles should be present (not None for live factors)
    live_fs = [f for f in fs if f["name"] != "lowvol"]
    assert all(f["percentile"] is not None for f in live_fs)


def test_in_screen_ticker_returns_5_factors(
    fake_screen_with_factors: dict[str, Any],
) -> None:
    from application.ticker_factors_use_case import ticker_factor_scores

    fs = ticker_factor_scores(
        "SPG", screen=fake_screen_with_factors, fetch_fn=_no_fetch
    )
    # Must return all 5 factors (4 live + lowvol)
    assert len(fs) == 5
    names = [f["name"] for f in fs]
    assert "lowvol" in names


def test_off_universe_ticker_live_computes_and_ranks(
    fake_screen_with_factors: dict[str, Any],
) -> None:
    from application.ticker_factors_use_case import ticker_factor_scores

    fs = ticker_factor_scores(
        "ZZZZ", screen=fake_screen_with_factors, fetch_fn=_fake_fetch
    )
    # Percentiles derived by ranking live z against the cohort — must be in [0, 1]
    live_fs = [f for f in fs if f["name"] != "lowvol" and f["percentile"] is not None]
    assert all(0.0 <= f["percentile"] <= 1.0 for f in live_fs)
    # lowvol has no data — should be DATA-GAP
    lowvol = next(f for f in fs if f["name"] == "lowvol")
    assert lowvol["percentile"] is None


def test_missing_data_is_data_gap(
    fake_screen_with_factors: dict[str, Any],
) -> None:
    from application.ticker_factors_use_case import ticker_factor_scores

    fs = ticker_factor_scores(
        "NODATA", screen=fake_screen_with_factors, fetch_fn=_fetch_raises
    )
    # All factors should be DATA-GAP (None) — no fabricated values
    assert all(f["percentile"] is None for f in fs)
    assert all(f["value"] is None for f in fs)


def test_off_universe_returns_5_factors(
    fake_screen_with_factors: dict[str, Any],
) -> None:
    from application.ticker_factors_use_case import ticker_factor_scores

    fs = ticker_factor_scores(
        "ZZZZ", screen=fake_screen_with_factors, fetch_fn=_fake_fetch
    )
    assert len(fs) == 5


def test_in_screen_subtitle_flag(
    fake_screen_with_factors: dict[str, Any],
) -> None:
    """in-screen tickers carry source='screen', off-universe carry source='live'."""
    from application.ticker_factors_use_case import ticker_factor_scores

    fs_in = ticker_factor_scores(
        "SPG", screen=fake_screen_with_factors, fetch_fn=_no_fetch
    )
    fs_off = ticker_factor_scores(
        "ZZZZ", screen=fake_screen_with_factors, fetch_fn=_fake_fetch
    )
    # Each row should carry a source key indicating where the data came from
    assert all(f.get("source") == "screen" for f in fs_in)
    assert all(f.get("source") == "live" for f in fs_off)
