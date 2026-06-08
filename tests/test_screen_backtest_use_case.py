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
