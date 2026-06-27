# tests/domain/test_screener_composite_service.py
from __future__ import annotations

from datetime import date

from domain.corroboration_models import ConvergenceTier
from domain.screen_models import FactorScore, ScreenCandidate, ScreenLabel, ScreenResult
from domain.screened_row import CorroborationSnapshot
from domain.screener_composite_service import ScreenerCompositeService


def _cand(ticker: str, composite: float) -> ScreenCandidate:
    fs = FactorScore(name="momentum", value=composite, percentile=0.5, contribution=0.2)
    return ScreenCandidate(
        ticker=ticker,
        composite=composite,
        factor_scores=(fs,),
        trend_health=0.5,
        why="",
        label=ScreenLabel.RESEARCH_ONLY,
    )


def _result(*composites: tuple[str, float]) -> ScreenResult:
    cands = tuple(_cand(t, c) for t, c in composites)
    return ScreenResult(
        as_of="2026-06-22",
        candidates=cands,
        universe_size=100,
        regime="NEUTRAL",
        scorecard_ref=None,
        abstained=False,
        diagnostics=None,
    )


def _snap(ticker: str, tier: ConvergenceTier) -> CorroborationSnapshot:
    return CorroborationSnapshot(
        ticker=ticker,
        convergence_tier=tier,
        n_sources=3,
        surfaced_at=date(2026, 6, 21),
    )


AS_OF = date(2026, 6, 22)


def test_compose_no_corroboration_preserves_factor_order() -> None:
    result = _result(("AAPL", 1.8), ("MSFT", 1.2), ("GOOG", 0.6))
    svc = ScreenerCompositeService()
    rows = svc.compose(result, [], AS_OF)
    assert [r.candidate.ticker for r in rows] == ["AAPL", "MSFT", "GOOG"]
    assert all(r.factor_only for r in rows)


def test_compose_strong_corroboration_boosts_rank() -> None:
    result = _result(("AAPL", 1.8), ("MSFT", 1.2), ("GOOG", 0.6))
    snaps = [_snap("GOOG", ConvergenceTier.STRONG)]
    svc = ScreenerCompositeService()
    rows = svc.compose(result, snaps, AS_OF)
    assert rows[0].candidate.ticker == "AAPL"
    goog_row = next(r for r in rows if r.candidate.ticker == "GOOG")
    assert not goog_row.factor_only
    assert goog_row.corroboration is not None


def test_compose_stale_corroboration_outside_window_ignored() -> None:
    result = _result(("AAPL", 1.8))
    stale_snap = CorroborationSnapshot(
        ticker="AAPL",
        convergence_tier=ConvergenceTier.STRONG,
        n_sources=3,
        surfaced_at=date(2026, 6, 10),
    )
    svc = ScreenerCompositeService()
    rows = svc.compose(result, [stale_snap], AS_OF, window_days=7)
    assert rows[0].factor_only is True


def test_compose_within_window_accepted() -> None:
    result = _result(("AAPL", 1.8))
    fresh_snap = CorroborationSnapshot(
        ticker="AAPL",
        convergence_tier=ConvergenceTier.STRONG,
        n_sources=3,
        surfaced_at=date(2026, 6, 17),
    )
    svc = ScreenerCompositeService()
    rows = svc.compose(result, [fresh_snap], AS_OF, window_days=7)
    assert rows[0].factor_only is False


def test_compose_empty_candidates_returns_empty() -> None:
    result = _result()
    svc = ScreenerCompositeService()
    rows = svc.compose(result, [], AS_OF)
    assert rows == ()
