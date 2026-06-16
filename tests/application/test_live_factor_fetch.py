"""TDD tests for off-universe live factor fetch (feat/dashboard-legibility-redesign).

Tests cover:
1. ticker_factor_scores with a FAKE fetch_fn for off-universe ticker → ranked percentiles.
2. ticker_factor_scores DATA-GAP where fake returns None for a factor.
3. batch_fit(live_fetch=True) populates factor_scores for off-universe via injected fake.
4. lowvol inversion sign: calmer stock (lower volatility) → higher lowvol raw z-score.
5. live_factor_fetch_fn() returns a callable that accepts a ticker (no network called).

NO yfinance/network calls — all adapters are fakes.
"""

from __future__ import annotations

from typing import Any

import pytest

# ---------------------------------------------------------------------------
# Shared fakes & fixtures
# ---------------------------------------------------------------------------

_COHORT_FACTORS = [
    {
        "name": "momentum",
        "value": 0.2,
        "percentile": 0.50,
        "source": "screen",
    },
    {
        "name": "revision",
        "value": 0.4,
        "percentile": 0.50,
        "source": "screen",
    },
    {
        "name": "quality",
        "value": 0.6,
        "percentile": 0.50,
        "source": "screen",
    },
    {
        "name": "value",
        "value": 0.1,
        "percentile": 0.50,
        "source": "screen",
    },
    {
        "name": "lowvol",
        "value": -0.5,
        "percentile": 0.30,
        "source": "screen",
    },
]


@pytest.fixture()
def two_candidate_screen() -> dict[str, Any]:
    """A minimal screen with two in-universe candidates."""
    return {
        "as_of": "2026-06-15",
        "candidates": [
            {"ticker": "AAPL", "factor_scores": _COHORT_FACTORS},
            {
                "ticker": "MSFT",
                "factor_scores": [
                    {
                        "name": "momentum",
                        "value": 0.8,
                        "percentile": 0.80,
                        "source": "screen",
                    },
                    {
                        "name": "revision",
                        "value": 1.0,
                        "percentile": 0.80,
                        "source": "screen",
                    },
                    {
                        "name": "quality",
                        "value": 1.2,
                        "percentile": 0.80,
                        "source": "screen",
                    },
                    {
                        "name": "value",
                        "value": 0.5,
                        "percentile": 0.80,
                        "source": "screen",
                    },
                    {
                        "name": "lowvol",
                        "value": -0.3,
                        "percentile": 0.60,
                        "source": "screen",
                    },
                ],
            },
        ],
    }


def _fake_full_fetch(ticker: str) -> dict[str, float | None]:
    """Fake fetch_fn: returns raw z-scores for ANY off-universe ticker, all present."""
    return {
        "momentum": 0.5,
        "revision": 0.7,
        "quality": 0.9,
        "value": 0.3,
        "lowvol": -0.4,  # inverted: calmer → higher (less negative)
    }


def _fake_partial_fetch(ticker: str) -> dict[str, float | None]:
    """Fake fetch_fn: momentum and revision present; quality/value/lowvol are None."""
    return {
        "momentum": 0.5,
        "revision": 0.7,
        "quality": None,
        "value": None,
        "lowvol": None,
    }


def _fake_calm_fetch(ticker: str) -> dict[str, float | None]:
    """Returns a calm (low-vol) stock: lowvol = positive (inverted vol is higher)."""
    return {
        "momentum": 0.0,
        "revision": 0.0,
        "quality": 0.0,
        "value": 0.0,
        "lowvol": 0.8,  # calmer: inverted vol is positive / high
    }


def _fake_volatile_fetch(ticker: str) -> dict[str, float | None]:
    """Returns a volatile stock: lowvol = negative (inverted vol is lower)."""
    return {
        "momentum": 0.0,
        "revision": 0.0,
        "quality": 0.0,
        "value": 0.0,
        "lowvol": -1.5,  # more volatile: inverted vol is negative / low
    }


# ---------------------------------------------------------------------------
# 1. ticker_factor_scores — off-universe with full fake fetch → ranked percentiles
# ---------------------------------------------------------------------------


def test_off_universe_all_present_yields_percentiles(
    two_candidate_screen: dict[str, Any],
) -> None:
    """Off-universe ticker with all factors present → percentiles in [0, 1]."""
    from application.ticker_factors_use_case import ticker_factor_scores

    fs = ticker_factor_scores(
        "ZZZZ", screen=two_candidate_screen, fetch_fn=_fake_full_fetch
    )
    assert len(fs) == 5
    for row in fs:
        assert row["percentile"] is not None, f"Expected percentile for {row['name']}"
        assert (
            0.0 <= row["percentile"] <= 1.0
        ), f"Percentile out of range for {row['name']}: {row['percentile']}"
    # All rows are from live compute
    assert all(row["source"] == "live" for row in fs)


def test_off_universe_value_field_carries_raw_z(
    two_candidate_screen: dict[str, Any],
) -> None:
    """The 'value' field in the off-universe result equals the raw z from fetch_fn."""
    from application.ticker_factors_use_case import ticker_factor_scores

    fs = ticker_factor_scores(
        "ZZZZ", screen=two_candidate_screen, fetch_fn=_fake_full_fetch
    )
    raw = _fake_full_fetch("ZZZZ")
    for row in fs:
        expected_raw = raw[row["name"]]
        assert (
            row["value"] == expected_raw
        ), f"Factor {row['name']}: expected raw z {expected_raw}, got {row['value']}"


# ---------------------------------------------------------------------------
# 2. DATA-GAP: fetch_fn returns None for some factors
# ---------------------------------------------------------------------------


def test_off_universe_partial_fetch_none_factors_are_data_gap(
    two_candidate_screen: dict[str, Any],
) -> None:
    """Where fetch_fn returns None for a factor, percentile and value are None."""
    from application.ticker_factors_use_case import ticker_factor_scores

    fs = ticker_factor_scores(
        "ZZZZ", screen=two_candidate_screen, fetch_fn=_fake_partial_fetch
    )
    # momentum and revision are present
    mom = next(r for r in fs if r["name"] == "momentum")
    rev = next(r for r in fs if r["name"] == "revision")
    assert mom["percentile"] is not None
    assert rev["percentile"] is not None

    # quality, value, lowvol are DATA-GAP
    for fname in ("quality", "value", "lowvol"):
        row = next(r for r in fs if r["name"] == fname)
        assert row["value"] is None, f"{fname} value should be None (DATA-GAP)"
        assert (
            row["percentile"] is None
        ), f"{fname} percentile should be None (DATA-GAP)"


# ---------------------------------------------------------------------------
# 3. batch_fit with live_fetch=True and injected fake fetch_fn
# ---------------------------------------------------------------------------


def test_batch_fit_live_fetch_populates_off_universe_factor_scores(
    two_candidate_screen: dict[str, Any],
) -> None:
    """batch_fit(live_fetch=True, fetch_fn=fake) populates factor_scores for off-universe."""
    from application.batch_fit_use_case import batch_fit
    from domain.fit import FitVerdict

    def _fit_fn(t: str) -> FitVerdict:
        return FitVerdict(
            ticker=t, evidence_grade="MODERATE", fit_flags=(), summary=f"{t} ok."
        )

    # GOOG is NOT in the screen — off-universe
    rows = batch_fit(
        ["GOOG"],
        fit_fn=_fit_fn,
        screen=two_candidate_screen,
        live_fetch=True,
        fetch_fn=_fake_full_fetch,
    )
    assert len(rows) == 1
    row = rows[0]
    assert row.ticker == "GOOG"
    # factor_scores must be populated (not empty) for off-universe with live_fetch
    assert len(row.factor_scores) == 5
    # All five factors are returned
    names = {f["name"] for f in row.factor_scores}
    assert names == {"momentum", "revision", "quality", "value", "lowvol"}


def test_batch_fit_live_fetch_in_universe_ticker_uses_screen_data(
    two_candidate_screen: dict[str, Any],
) -> None:
    """In-universe ticker still uses stored factor_scores regardless of live_fetch flag."""
    from application.batch_fit_use_case import batch_fit
    from domain.fit import FitVerdict

    fetch_called: list[str] = []

    def _tracking_fetch(t: str) -> dict[str, float | None]:
        fetch_called.append(t)
        return _fake_full_fetch(t)

    def _fit_fn(t: str) -> FitVerdict:
        return FitVerdict(
            ticker=t, evidence_grade="MODERATE", fit_flags=(), summary=f"{t} ok."
        )

    # AAPL IS in the screen
    rows = batch_fit(
        ["AAPL"],
        fit_fn=_fit_fn,
        screen=two_candidate_screen,
        live_fetch=True,
        fetch_fn=_tracking_fetch,
    )
    assert len(rows) == 1
    row = rows[0]
    assert row.ticker == "AAPL"
    # factor_scores are from screen, not live
    for fs in row.factor_scores:
        assert fs.get("source") == "screen"
    # fetch_fn should NOT have been called for an in-universe ticker
    assert (
        "AAPL" not in fetch_called
    ), "fetch_fn must not be called for in-universe ticker AAPL"


def test_batch_fit_default_behaviour_unchanged(
    two_candidate_screen: dict[str, Any],
) -> None:
    """Default batch_fit (no live_fetch) still returns DATA-GAP for off-universe."""
    from application.batch_fit_use_case import batch_fit
    from domain.fit import FitVerdict

    def _fit_fn(t: str) -> FitVerdict:
        return FitVerdict(
            ticker=t, evidence_grade="MODERATE", fit_flags=(), summary=f"{t} ok."
        )

    rows = batch_fit(
        ["ZZZZ"],
        fit_fn=_fit_fn,
        screen=two_candidate_screen,
        # live_fetch not passed — defaults to False
    )
    assert len(rows) == 1
    row = rows[0]
    # Off-universe with no live fetch → all factors are DATA-GAP
    for fs in row.factor_scores:
        assert fs["value"] is None, f"Expected DATA-GAP for {fs['name']}"
        assert fs["percentile"] is None


# ---------------------------------------------------------------------------
# 4. lowvol inversion: calmer stock → higher lowvol value
# ---------------------------------------------------------------------------


def test_lowvol_inversion_calmer_ranks_higher(
    two_candidate_screen: dict[str, Any],
) -> None:
    """Calmer stock (higher lowvol z-score) ranks above volatile stock."""
    from application.ticker_factors_use_case import ticker_factor_scores

    fs_calm = ticker_factor_scores(
        "CALM", screen=two_candidate_screen, fetch_fn=_fake_calm_fetch
    )
    fs_vol = ticker_factor_scores(
        "NOISY", screen=two_candidate_screen, fetch_fn=_fake_volatile_fetch
    )

    calm_lowvol = next(r for r in fs_calm if r["name"] == "lowvol")
    noisy_lowvol = next(r for r in fs_vol if r["name"] == "lowvol")

    # Both should have values (not DATA-GAP)
    assert calm_lowvol["value"] is not None
    assert noisy_lowvol["value"] is not None

    # Calmer stock has higher raw lowvol z (because vol is inverted: -vol)
    assert calm_lowvol["value"] > noisy_lowvol["value"], (
        f"Calmer stock lowvol z ({calm_lowvol['value']}) should exceed "
        f"volatile stock's ({noisy_lowvol['value']})"
    )

    # And correspondingly higher percentile when ranked vs the same cohort
    assert calm_lowvol["percentile"] is not None
    assert noisy_lowvol["percentile"] is not None
    assert (
        calm_lowvol["percentile"] >= noisy_lowvol["percentile"]
    ), "Calmer stock should rank >= volatile stock on lowvol percentile"


# ---------------------------------------------------------------------------
# 5. live_factor_fetch_fn() is importable and returns a callable
# ---------------------------------------------------------------------------


def test_live_factor_fetch_fn_returns_callable() -> None:
    """live_factor_fetch_fn() must return a Callable without hitting the network."""
    from application.ticker_factors_use_case import live_factor_fetch_fn

    fn = live_factor_fetch_fn()
    assert callable(fn), "live_factor_fetch_fn() must return a callable"


def test_live_factor_fetch_fn_signature() -> None:
    """live_factor_fetch_fn() callable's return type contract is documented."""
    import inspect

    from application.ticker_factors_use_case import live_factor_fetch_fn

    fn = live_factor_fetch_fn()
    sig = inspect.signature(fn)
    params = list(sig.parameters.keys())
    # Must accept exactly one positional parameter (ticker: str)
    assert len(params) == 1, f"Expected 1 param, got {params}"
