from domain.screen_diagnostics import ScreenDiagnostics, ScreenVerdict, classify_screen


def test_under_powered_when_history_coverage_low():
    d = ScreenDiagnostics(scanned=512, had_history=20, above_trend=0, cleared=0)
    assert classify_screen(d, coverage_floor=0.5) is ScreenVerdict.UNDER_POWERED


def test_earned_abstention_when_coverage_healthy_but_zero_cleared():
    d = ScreenDiagnostics(scanned=512, had_history=490, above_trend=0, cleared=0)
    assert classify_screen(d, coverage_floor=0.5) is ScreenVerdict.EARNED_ABSTENTION


def test_has_candidates_when_cleared_positive():
    d = ScreenDiagnostics(scanned=512, had_history=490, above_trend=300, cleared=70)
    assert classify_screen(d, coverage_floor=0.5) is ScreenVerdict.HAS_CANDIDATES


def test_coverage_floor_boundary_is_inclusive_healthy():
    d = ScreenDiagnostics(scanned=100, had_history=50, above_trend=0, cleared=0)
    assert classify_screen(d, coverage_floor=0.5) is ScreenVerdict.EARNED_ABSTENTION


def test_diagnostics_rejects_impossible_counts():
    import pytest

    with pytest.raises(ValueError):
        ScreenDiagnostics(scanned=10, had_history=20, above_trend=0, cleared=0)
