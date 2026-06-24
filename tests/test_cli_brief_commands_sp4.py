"""SP4 Task 4: renderer tests for inline corroboration evidence + tilt section + footer."""

from __future__ import annotations

from domain.brief import (
    HoldingVerdictLine,
    ScorecardSnapshot,
    WeeklyBrief,
    to_markdown,
    to_stdout_masked,
)
from domain.corroboration_models import ConvergenceTier, DirectionalView, Stance
from domain.discipline import Verdict
from domain.regime import Regime
from domain.screen_models import ScreenLabel

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _holding(
    ticker: str = "AAPL",
    verdict: Verdict = Verdict.HOLD,
    tier: ConvergenceTier | None = None,
    n: int | None = None,
    stance: Stance | None = None,
) -> HoldingVerdictLine:
    return HoldingVerdictLine(
        ticker=ticker,
        unrealized_pct=0.12,
        trend_state="uptrend",
        verdict=verdict,
        why="momentum ok",
        convergence_tier=tier,
        n_sources=n,
        source_stance=stance,
    )


def _view(
    name: str = "Technology",
    tilt: str = "LEAN_IN",
    stance: Stance = Stance.BULLISH,
    tier: ConvergenceTier = ConvergenceTier.STRONG,
    yours: float = 0.08,
) -> DirectionalView:
    return DirectionalView(
        group_kind="sector",
        group_name=name,
        net_stance=stance,
        mean_convergence=1.0,
        your_exposure_pct=yours,
        evidence_weight_pct=100.0,
        tilt=tilt,
    )


def _minimal_brief(
    holdings: list[HoldingVerdictLine],
    views: list[DirectionalView] | None = None,
) -> WeeklyBrief:
    """Build a minimal WeeklyBrief for renderer tests — direct construction, no assemble_brief."""
    return WeeklyBrief(
        as_of="2026-06-23",
        regime=Regime.NEUTRAL,
        tilt={"momentum": 0.5, "revision": 0.3, "quality": 0.1, "value": 0.1},
        candidates=(),
        holdings=tuple(holdings),
        research_links=(),
        concentration=(),
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
        screen_label=ScreenLabel.RESEARCH_ONLY,
        directional_views=tuple(views or []),
    )


# ---------------------------------------------------------------------------
# to_markdown — inline sources per holding
# ---------------------------------------------------------------------------


def test_to_markdown_shows_inline_sources_for_corroborated_holding() -> None:
    h = _holding(tier=ConvergenceTier.STRONG, n=3, stance=Stance.BULLISH)
    brief = _minimal_brief([h])
    md = to_markdown(brief)
    assert "│ sources: BULLISH ×3 [STRONG]" in md


def test_to_markdown_no_sources_segment_when_no_snapshot() -> None:
    h = _holding()  # no corroboration
    brief = _minimal_brief([h])
    md = to_markdown(brief)
    assert "│ sources:" not in md


def test_to_markdown_shows_conflict_marker() -> None:
    h = _holding(
        verdict=Verdict.REDUCE,
        tier=ConvergenceTier.MODERATE,
        n=2,
        stance=Stance.BULLISH,
    )
    brief = _minimal_brief([h])
    md = to_markdown(brief)
    assert "⚠ CONFLICT" in md


def test_to_markdown_no_conflict_when_aligned() -> None:
    h = _holding(
        verdict=Verdict.HOLD,
        tier=ConvergenceTier.STRONG,
        n=3,
        stance=Stance.BULLISH,
    )
    brief = _minimal_brief([h])
    md = to_markdown(brief)
    assert "⚠ CONFLICT" not in md


# ---------------------------------------------------------------------------
# to_markdown — tilt section
# ---------------------------------------------------------------------------


def test_to_markdown_shows_tilt_section() -> None:
    view = _view("Technology", "LEAN_IN", Stance.BULLISH)
    brief = _minimal_brief([_holding()], views=[view])
    md = to_markdown(brief)
    assert "Directional Tilts" in md
    assert "LEAN_IN" in md
    assert "Technology" in md
    assert "RESEARCH_ONLY" in md


def test_to_markdown_no_tilt_section_when_no_views() -> None:
    brief = _minimal_brief([_holding()])
    md = to_markdown(brief)
    assert "Directional Tilts" not in md


# ---------------------------------------------------------------------------
# to_markdown — footer
# ---------------------------------------------------------------------------


def test_to_markdown_footer_when_missing_snapshots() -> None:
    h1 = _holding("AAPL", tier=ConvergenceTier.STRONG, n=3, stance=Stance.BULLISH)
    h2 = _holding("MSFT")  # no snapshot
    brief = _minimal_brief([h1, h2])
    md = to_markdown(brief)
    assert "1 holding(s) have no corroboration snapshot" in md


def test_to_markdown_no_footer_when_all_corroborated() -> None:
    h = _holding(tier=ConvergenceTier.STRONG, n=3, stance=Stance.BULLISH)
    brief = _minimal_brief([h])
    md = to_markdown(brief)
    assert "no corroboration snapshot" not in md


# ---------------------------------------------------------------------------
# to_stdout_masked — tilt section + no per-holding leak
# ---------------------------------------------------------------------------


def test_to_stdout_masked_shows_tilt_section() -> None:
    view = _view("Energy", "LEAN_OUT", Stance.BEARISH)
    brief = _minimal_brief([_holding()], views=[view])
    out = to_stdout_masked(brief)
    assert "Directional Tilts" in out
    assert "LEAN_OUT" in out
    assert "Energy" in out


def test_to_stdout_masked_no_per_holding_sources() -> None:
    # Masked output must never reveal per-holding ticker or sources detail
    h = _holding(tier=ConvergenceTier.STRONG, n=3, stance=Stance.BULLISH)
    brief = _minimal_brief([h])
    out = to_stdout_masked(brief)
    assert "│ sources:" not in out
    assert "AAPL" not in out  # ticker must remain masked
