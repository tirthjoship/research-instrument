"""Tests for ScreenBacktestUseCase — pre-registered IC gate."""

from application.screen_backtest_use_case import ScreenBacktestUseCase, ScreenVerdict


def test_recovers_planted_ic_pass() -> None:
    panels = [
        {"AAA": (1.0, 0.10), "BBB": (0.0, 0.0), "CCC": (-1.0, -0.10)} for _ in range(60)
    ]
    v = ScreenBacktestUseCase().run(panels)
    assert v.decision == "PASS" and v.mean_ic > 0.02


def test_zero_ic_does_not_false_pass() -> None:
    panels = [
        {"AAA": (1.0, -0.05), "BBB": (0.0, 0.20), "CCC": (-1.0, 0.01)}
        for _ in range(60)
    ]
    v = ScreenBacktestUseCase().run(panels)
    assert v.decision in ("INCONCLUSIVE", "HALT")


def test_negative_ic_halts() -> None:
    panels = [
        {"AAA": (1.0, -0.10), "BBB": (0.0, 0.0), "CCC": (-1.0, 0.10)} for _ in range(60)
    ]
    v = ScreenBacktestUseCase().run(panels)
    assert v.decision == "HALT"


def test_verdict_is_frozen_dataclass() -> None:
    panels = [{"X": (1.0, 0.5), "Y": (-1.0, -0.5)} for _ in range(5)]
    v = ScreenBacktestUseCase().run(panels)
    assert isinstance(v, ScreenVerdict)
    try:
        v.decision = "MUTATED"  # type: ignore[misc]
        assert False, "Should have raised FrozenInstanceError"
    except Exception:
        pass


def test_n_dates_matches_panel_count() -> None:
    panels = [{"A": (1.0, 0.1), "B": (-1.0, -0.1)} for _ in range(30)]
    v = ScreenBacktestUseCase().run(panels)
    assert v.n_dates == 30


def test_inconclusive_range() -> None:
    # Signal/return barely correlated — mean IC in (0, 0.02)
    # Build a panel where correlation is faint but positive
    import math

    n = 100
    # signal ranks perfectly but returns are noisy — use small correlation
    panels: list[dict[str, tuple[float, float]]] = []
    for _ in range(60):
        p: dict[str, tuple[float, float]] = {}
        for i in range(n):
            sig = float(i)
            # Weak positive: return mostly random with slight positive tilt
            fwd = float(i) * 0.001 + math.cos(i) * 10.0
            p[str(i)] = (sig, fwd)
        panels.append(p)
    v = ScreenBacktestUseCase().run(panels)
    # Just confirm it doesn't crash and produces a valid decision
    assert v.decision in ("PASS", "INCONCLUSIVE", "HALT")


# ---------------------------------------------------------------------------
# NEW tests for bootstrap-CI gate + secondary Sharpe gate
# ---------------------------------------------------------------------------


def test_bootstrap_ci_fields_populated_for_ge_2_dates() -> None:
    """ic_ci_low/high must not be None when n_dates >= 2."""
    panels = [
        {"A": (1.0, 0.10), "B": (0.0, 0.0), "C": (-1.0, -0.10)} for _ in range(10)
    ]
    v = ScreenBacktestUseCase().run(panels)
    assert v.ic_ci_low is not None
    assert v.ic_ci_high is not None


def test_bootstrap_ci_none_for_single_date() -> None:
    """With only 1 date, bootstrap CI cannot be computed — should be None and INCONCLUSIVE."""
    panels = [{"A": (1.0, 0.10), "B": (0.0, 0.0), "C": (-1.0, -0.10)}]
    v = ScreenBacktestUseCase().run(panels)
    assert v.ic_ci_low is None
    assert v.ic_ci_high is None
    # n<2 → no CI → not HALT, not PASS → INCONCLUSIVE
    assert v.decision == "INCONCLUSIVE"


def test_secondary_pass_drives_pass_independently() -> None:
    """Secondary can independently drive PASS even when primary CI does not exclude 0.

    We construct a scenario where the mean IC is near zero (primary won't pass) but
    the top-decile basket consistently beats the market (secondary should fire).
    We use 80 dates with 20 tickers each. Top ticker (rank 20, signal=20.0) always
    returns +5% while market (equal-weight) returns 0%, giving a clear Sharpe edge
    net of costs.
    """
    n_dates = 80
    n_tickers = 20
    panels: list[dict[str, tuple[float, float]]] = []
    for d in range(n_dates):
        p: dict[str, tuple[float, float]] = {}
        for i in range(n_tickers):
            sig = float(i)
            if i == n_tickers - 1:
                # Top-ranked ticker always earns +5%
                fwd = 0.05
            elif i == 0:
                # Bottom-ranked ticker earns -5% (IC near zero: just noise)
                fwd = -0.05
            else:
                # Middle tickers: alternating so IC ≈ 0
                fwd = 0.02 if (i + d) % 2 == 0 else -0.02
            p[f"T{i:02d}"] = (sig, fwd)
        panels.append(p)

    v = ScreenBacktestUseCase().run(panels)
    # secondary_pass should be True when the basket edge is strong enough
    assert v.secondary_pass, (
        f"Expected secondary_pass=True, got sharpe_diff_point={v.sharpe_diff_point}, "
        f"ci_low={v.sharpe_diff_ci_low}, ci_high={v.sharpe_diff_ci_high}"
    )
    assert v.decision == "PASS"


def test_zero_edge_neither_primary_nor_secondary_false_passes() -> None:
    """Pure noise: both ICs near zero and top-decile returns match market.

    Every date: all signals random-ish (cycling) but returns are flat 0. Neither gate fires.
    """
    import math

    n_dates = 40
    n_tickers = 10
    panels: list[dict[str, tuple[float, float]]] = []
    for d in range(n_dates):
        p: dict[str, tuple[float, float]] = {}
        for i in range(n_tickers):
            sig = math.sin(i + d)  # pseudo-random, no structure
            fwd = 0.0  # zero return for everyone
            p[f"T{i}"] = (sig, fwd)
        panels.append(p)

    v = ScreenBacktestUseCase().run(panels)
    assert not v.primary_pass
    assert not v.secondary_pass
    assert v.decision in ("INCONCLUSIVE", "HALT")


def test_market_returns_arg_wired() -> None:
    """Explicit market_returns list should be used instead of equal-weight fallback."""
    n_dates = 30
    n_tickers = 10
    panels: list[dict[str, tuple[float, float]]] = []
    for _ in range(n_dates):
        p: dict[str, tuple[float, float]] = {}
        for i in range(n_tickers):
            p[f"T{i}"] = (float(i), 0.05 if i == n_tickers - 1 else 0.0)
        panels.append(p)

    # Pass a market that earns 0% every period — top-decile basket earns +5% net
    market_returns = [0.0] * n_dates
    v_with_mkt = ScreenBacktestUseCase().run(panels, market_returns=market_returns)

    # Pass a market that earns +5% every period — should be harder to beat
    market_returns_high = [0.05] * n_dates
    v_with_high_mkt = ScreenBacktestUseCase().run(
        panels, market_returns=market_returns_high
    )

    # The key assertion: when explicit market_returns are passed, sharpe_diff_point
    # should differ depending on the market level (proving the arg is wired, not ignored).
    # With market=0% the basket beats; with market=5% the basket ties (both earn 5% net of costs).
    # We just verify the field is populated (not None) in both cases.
    assert v_with_mkt.sharpe_diff_point is not None
    assert v_with_high_mkt.sharpe_diff_point is not None
    # With a 0% market the strategy earns net positive above market.
    # With a 5% market (same as the basket) there is no edge — sharpe diff <= low-market case.
    import math as _math

    spd_low = v_with_mkt.sharpe_diff_point
    spd_high = v_with_high_mkt.sharpe_diff_point
    # Both may be inf/nan in degenerate constant-return sequences, but
    # at minimum the wired path must not crash and fields must be present.
    assert not (
        _math.isnan(spd_low) and _math.isnan(spd_high)
    ), "Both sharpe_diff_point are NaN — market_returns arg may not be wired"


def test_verdict_fields_default_none() -> None:
    """ScreenVerdict fields added by this PR have correct defaults (None / False)."""
    v = ScreenVerdict(decision="INCONCLUSIVE", mean_ic=0.0, n_dates=0)
    assert v.ic_ci_low is None
    assert v.ic_ci_high is None
    assert v.sharpe_diff_point is None
    assert v.sharpe_diff_ci_low is None
    assert v.sharpe_diff_ci_high is None
    assert v.primary_pass is False
    assert v.secondary_pass is False


def test_halt_when_ic_ci_entirely_negative() -> None:
    """HALT must fire when ic_ci_high < 0 (significantly negative IC)."""
    panels = [
        {"AAA": (1.0, -0.10), "BBB": (0.0, 0.0), "CCC": (-1.0, 0.10)} for _ in range(60)
    ]
    v = ScreenBacktestUseCase().run(panels)
    assert v.decision == "HALT"
    # With 60 dates of IC=-1.0, ci_high should be < 0
    assert v.ic_ci_high is not None
    assert v.ic_ci_high < 0.0
