"""SP4 Task 2: corroboration fields on HoldingVerdictLine + WeeklyBrief."""

from __future__ import annotations

from datetime import date
from typing import Any

import pytest

from domain.brief import HoldingVerdictLine, ScorecardSnapshot, assemble_brief
from domain.corroboration_models import ConvergenceTier, DirectionalView, Stance
from domain.discipline import Verdict
from domain.models import PortfolioRisk, PositionRisk
from domain.regime import Regime
from domain.screen_models import ScreenLabel, ScreenResult
from domain.screened_row import CorroborationSnapshot

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_snapshot(
    ticker: str,
    tier: ConvergenceTier = ConvergenceTier.STRONG,
    n: int = 3,
    stance: Stance = Stance.BULLISH,
) -> CorroborationSnapshot:
    return CorroborationSnapshot(
        ticker=ticker,
        convergence_tier=tier,
        n_sources=n,
        surfaced_at=date(2026, 6, 23),
        net_stance=stance,
    )


def _make_position(ticker: str = "AAPL") -> PositionRisk:
    return PositionRisk(
        ticker=ticker,
        price=150.0,
        verdict=Verdict.HOLD,
        confidence=0.6,
        trend_health=0.5,
        vol_signal=0.1,
        relative_strength=None,
        downside_to_stop=0.05,
        upside_to_recover=0.10,
        behavior_flags=(),
        unrealized_pct=0.12,
        account_type="TFSA",
        abstained=False,
        why="ok",
    )


@pytest.fixture
def minimal_brief_kwargs() -> dict[str, Any]:
    return dict(
        as_of="2026-06-23",
        regime=Regime.RISK_ON,
        tilt={"momentum": 0.5, "revision": 0.3, "quality": 0.1, "value": 0.1},
        screen_result=ScreenResult(
            as_of="2026-06-23",
            candidates=(),
            universe_size=0,
            regime="RISK_ON",
            scorecard_ref=None,
            abstained=False,
        ),
        screen_label=ScreenLabel.RESEARCH_ONLY,
        top_n=5,
        positions=[_make_position("AAPL")],
        portfolio=PortfolioRisk(
            n_positions=1,
            broken_trend_share=0.0,
            top_concentration=0.10,
            verdict_counts={},
        ),
        held_tickers={"AAPL"},
        cluster_overlaps={},
        scorecard=ScorecardSnapshot(
            screen_window="2026-06-23",
            screen_top_ret=None,
            screen_spy_ret=None,
            screen_n=0,
            screen_significant=False,
            discipline_window="21d",
            discipline_reduce_down_rate=None,
            discipline_n=0,
            discipline_gate_status="OPEN",
        ),
    )


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_holding_verdict_line_corroboration_fields_default_none() -> None:
    line = HoldingVerdictLine(
        ticker="AAPL",
        unrealized_pct=0.12,
        trend_state="uptrend",
        verdict=Verdict.HOLD,
        why="momentum ok",
    )
    assert line.convergence_tier is None
    assert line.n_sources is None
    assert line.source_stance is None


def test_assemble_brief_enriches_holdings_from_corroboration_map(
    minimal_brief_kwargs: dict[str, Any],
) -> None:
    snap = _make_snapshot("AAPL", ConvergenceTier.STRONG, 3, Stance.BULLISH)
    brief = assemble_brief(**minimal_brief_kwargs, corroboration_map={"AAPL": snap})
    aapl_line = next(h for h in brief.holdings if h.ticker == "AAPL")
    assert aapl_line.convergence_tier == ConvergenceTier.STRONG
    assert aapl_line.n_sources == 3
    assert aapl_line.source_stance == Stance.BULLISH


def test_assemble_brief_leaves_missing_tickers_as_none(
    minimal_brief_kwargs: dict[str, Any],
) -> None:
    # AAPL in holdings but no snapshot — fields remain None
    brief = assemble_brief(**minimal_brief_kwargs, corroboration_map={})
    aapl_line = next(h for h in brief.holdings if h.ticker == "AAPL")
    assert aapl_line.convergence_tier is None


def test_assemble_brief_no_corroboration_map_is_safe(
    minimal_brief_kwargs: dict[str, Any],
) -> None:
    brief = assemble_brief(**minimal_brief_kwargs)
    assert all(h.convergence_tier is None for h in brief.holdings)


def test_weekly_brief_directional_views_default_empty(
    minimal_brief_kwargs: dict[str, Any],
) -> None:
    brief = assemble_brief(**minimal_brief_kwargs)
    assert brief.directional_views == ()


def test_weekly_brief_stores_directional_views(
    minimal_brief_kwargs: dict[str, Any],
) -> None:
    view = DirectionalView(
        group_kind="sector",
        group_name="Technology",
        net_stance=Stance.BULLISH,
        mean_convergence=0.8,
        your_exposure_pct=0.15,
        evidence_weight_pct=0.25,
        tilt="LEAN_IN",
    )
    brief = assemble_brief(**minimal_brief_kwargs, directional_views=[view])
    assert len(brief.directional_views) == 1
    assert brief.directional_views[0].tilt == "LEAN_IN"
