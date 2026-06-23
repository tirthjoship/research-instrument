"""SP4 Task 3: CorroborationSnapshotFn + _build_directional_views in WeeklyBriefUseCase."""

from datetime import date, datetime
from typing import Any

import pytest

from application.holdings_reader import Holding
from application.weekly_brief_use_case import (
    RegimeReadUseCase,
    WeeklyBriefUseCase,
    _build_directional_views,
)
from domain.corroboration_models import ConvergenceTier, Stance
from domain.discipline import Verdict
from domain.models import PortfolioRisk, PositionRisk
from domain.screen_models import FactorScore, ScreenCandidate, ScreenLabel, ScreenResult
from domain.screened_row import CorroborationSnapshot

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _snap(ticker: str, tier: ConvergenceTier, stance: Stance) -> CorroborationSnapshot:
    return CorroborationSnapshot(
        ticker=ticker,
        convergence_tier=tier,
        n_sources=2,
        surfaced_at=date(2026, 6, 23),
        net_stance=stance,
    )


def _fs() -> tuple[FactorScore, ...]:
    return (
        FactorScore("momentum", 1.1, 0.82, 0.27),
        FactorScore("revision", 0.0, 0.0, 0.0),
        FactorScore("quality", 0.0, 0.0, 0.0),
        FactorScore("value", 0.0, 0.0, 0.0),
    )


class FakeSectorProvider:
    def __init__(self, mapping: dict[str, str]) -> None:
        self._m = mapping

    def sector(self, ticker: str) -> str:
        return self._m.get(ticker, "Unknown")


class _FakeScreen:
    def run(self, universe: list[str], as_of: str, top_n: int = 10) -> ScreenResult:
        cands = (
            ScreenCandidate(
                "AAPL", 0.42, _fs(), 1.3, "momentum", ScreenLabel.RESEARCH_ONLY
            ),
        )
        return ScreenResult(as_of, cands, 500, "NEUTRAL", None, False)


class _FakeHoldingsRisk:
    def execute(self, holdings: Any, start: Any, end: Any) -> dict[str, Any]:
        positions = [
            PositionRisk(
                "AAPL",
                200.0,
                Verdict.HOLD,
                0.6,
                1.4,
                0.0,
                0.1,
                0.2,
                0.3,
                (),
                0.15,
                "TFSA",
                False,
                "trend intact",
            ),
        ]
        return {
            "positions": positions,
            "portfolio": PortfolioRisk(1, 0.5, 0.22, {"HOLD": 1}),
        }


def minimal_execute_kwargs() -> dict[str, Any]:
    """Minimal keyword arguments for WeeklyBriefUseCase.execute()."""
    return dict(
        universe=["AAPL"],
        holdings=[Holding("AAPL", 10, 1000, "TFSA")],
        as_of=datetime(2026, 6, 23),
        report_dir="data/reports/",
        top_n=10,
    )


@pytest.fixture
def minimal_uc_kwargs() -> dict[str, Any]:
    """Minimal keyword arguments for WeeklyBriefUseCase.__init__()."""
    return dict(
        screen=_FakeScreen(),
        holdings_risk=_FakeHoldingsRisk(),
        regime_reader=RegimeReadUseCase(
            vix_provider=lambda: 20.0,
            spy_trend_provider=lambda: 0.1,
        ),
        screen_label_fn=lambda report_dir: ScreenLabel.RESEARCH_ONLY,
        cluster_peers_fn=lambda ticker: [],
        screen_scorecard_fn=lambda: (None, None, 0, False),
        discipline_scorecard_fn=lambda: (0.58, 5462, "PENDING"),
    )


# ---------------------------------------------------------------------------
# Tests: _build_directional_views (pure function)
# ---------------------------------------------------------------------------


def test_build_directional_views_lean_in() -> None:
    groups = {
        "Technology": [
            _snap("AAPL", ConvergenceTier.STRONG, Stance.BULLISH),
            _snap("MSFT", ConvergenceTier.STRONG, Stance.BULLISH),
        ]
    }
    exposure = {"Technology": 0.08}  # 8% — below evidence weight
    views = _build_directional_views(groups, exposure)
    assert len(views) == 1
    assert views[0].tilt == "LEAN_IN"
    assert views[0].group_name == "Technology"
    assert views[0].net_stance == Stance.BULLISH


def test_build_directional_views_lean_out() -> None:
    groups = {
        "Energy": [
            _snap("XOM", ConvergenceTier.MODERATE, Stance.BEARISH),
            _snap("CVX", ConvergenceTier.MODERATE, Stance.BEARISH),
        ]
    }
    exposure = {"Energy": 0.30}
    views = _build_directional_views(groups, exposure)
    assert views[0].tilt == "LEAN_OUT"


def test_build_directional_views_hold() -> None:
    groups = {"Healthcare": [_snap("JNJ", ConvergenceTier.WEAK, Stance.NEUTRAL)]}
    exposure = {"Healthcare": 0.10}
    views = _build_directional_views(groups, exposure)
    assert views[0].tilt == "HOLD"


def test_build_directional_views_empty_groups() -> None:
    assert _build_directional_views({}, {}) == []


# ---------------------------------------------------------------------------
# Tests: WeeklyBriefUseCase corroboration enrichment
# ---------------------------------------------------------------------------


def test_use_case_enriches_holdings_via_corroboration_fn(
    minimal_uc_kwargs: dict[str, Any],
) -> None:
    snap = _snap("AAPL", ConvergenceTier.STRONG, Stance.BULLISH)
    uc = WeeklyBriefUseCase(
        **minimal_uc_kwargs,
        corroboration_fn=lambda _: [snap],
        sector_provider=FakeSectorProvider({"AAPL": "Technology"}),
    )
    brief = uc.execute(**minimal_execute_kwargs())
    aapl = next(h for h in brief.holdings if h.ticker == "AAPL")
    assert aapl.convergence_tier == ConvergenceTier.STRONG
    assert aapl.source_stance == Stance.BULLISH


def test_use_case_no_corroboration_fn_safe(minimal_uc_kwargs: dict[str, Any]) -> None:
    uc = WeeklyBriefUseCase(**minimal_uc_kwargs)
    brief = uc.execute(**minimal_execute_kwargs())
    assert all(h.convergence_tier is None for h in brief.holdings)
    assert brief.directional_views == ()


def test_use_case_empty_corroboration_fn_safe(
    minimal_uc_kwargs: dict[str, Any],
) -> None:
    uc = WeeklyBriefUseCase(
        **minimal_uc_kwargs,
        corroboration_fn=lambda _: [],
    )
    brief = uc.execute(**minimal_execute_kwargs())
    assert all(h.convergence_tier is None for h in brief.holdings)
