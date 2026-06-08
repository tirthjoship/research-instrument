"""Tests for RegimeReadUseCase (Task 7) and WeeklyBriefUseCase (Task 8)."""

from datetime import datetime

from application.holdings_reader import Holding
from application.weekly_brief_use_case import RegimeReadUseCase, WeeklyBriefUseCase
from domain.brief import WeeklyBrief, to_markdown
from domain.discipline import Verdict
from domain.models import PortfolioRisk, PositionRisk
from domain.regime import Regime
from domain.screen_models import FactorScore, ScreenCandidate, ScreenLabel, ScreenResult

# ---------------------------------------------------------------------------
# Task 7: RegimeReadUseCase
# ---------------------------------------------------------------------------


def test_regime_read_uses_providers() -> None:
    uc = RegimeReadUseCase(
        vix_provider=lambda: 14.0,
        spy_trend_provider=lambda: 1.1,
    )
    assert uc.read() == Regime.RISK_ON


def test_regime_read_risk_off_on_high_vix() -> None:
    uc = RegimeReadUseCase(
        vix_provider=lambda: 32.0,
        spy_trend_provider=lambda: 0.6,
    )
    assert uc.read() == Regime.RISK_OFF


# ---------------------------------------------------------------------------
# Task 8: WeeklyBriefUseCase
# ---------------------------------------------------------------------------


def _fs() -> tuple[FactorScore, ...]:
    return (
        FactorScore("momentum", 1.1, 0.82, 0.27),
        FactorScore("revision", 0.0, 0.0, 0.0),
        FactorScore("quality", 0.0, 0.0, 0.0),
        FactorScore("value", 0.0, 0.0, 0.0),
    )


class _FakeScreen:
    def run(self, universe: list[str], as_of: str, top_n: int = 10) -> ScreenResult:
        cands = (
            ScreenCandidate(
                "AAPL", 0.42, _fs(), 1.3, "momentum", ScreenLabel.RESEARCH_ONLY
            ),
            ScreenCandidate(
                "NEW1", 0.30, _fs(), 0.9, "momentum", ScreenLabel.RESEARCH_ONLY
            ),
        )
        return ScreenResult(as_of, cands, 500, "NEUTRAL", None, False)


class _FakeHoldingsRisk:
    def execute(self, holdings, start, end):  # type: ignore[no-untyped-def]
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
            PositionRisk(
                "RIVN",
                10.0,
                Verdict.REDUCE,
                0.7,
                -1.2,
                0.0,
                -0.1,
                0.4,
                0.1,
                ("broken_trend",),
                -0.45,
                "Margin",
                False,
                "broken trend",
            ),
        ]
        return {
            "positions": positions,
            "portfolio": PortfolioRisk(2, 0.5, 0.22, {"HOLD": 1, "REDUCE": 1}),
        }


def _make_uc() -> WeeklyBriefUseCase:
    return WeeklyBriefUseCase(
        screen=_FakeScreen(),
        holdings_risk=_FakeHoldingsRisk(),
        regime_reader=RegimeReadUseCase(
            vix_provider=lambda: 20.0, spy_trend_provider=lambda: 0.1
        ),
        screen_label_fn=lambda report_dir: ScreenLabel.RESEARCH_ONLY,
        cluster_peers_fn=lambda ticker: ["AAPL"] if ticker == "NEW1" else [],
        screen_scorecard_fn=lambda: (
            None,
            None,
            0,
            False,
        ),  # (top_ret, spy_ret, n, significant)
        discipline_scorecard_fn=lambda: (
            0.58,
            5462,
            "PENDING",
        ),  # (down_rate, n, gate_status)
    )


def test_execute_returns_weekly_brief() -> None:
    uc = _make_uc()
    holdings = [Holding("AAPL", 10, 1000, "TFSA"), Holding("RIVN", 5, 500, "Margin")]
    brief = uc.execute(
        universe=["AAPL", "NEW1", "MSFT"],
        holdings=holdings,
        as_of=datetime(2026, 6, 8),
        report_dir="data/reports/",
        top_n=10,
    )
    assert isinstance(brief, WeeklyBrief)
    assert brief.screen_label == ScreenLabel.RESEARCH_ONLY
    # AAPL is held → already_held; NEW1 not held.
    assert any(c.ticker == "AAPL" and c.already_held for c in brief.candidates)
    # NEW1 clusters with held AAPL → a concentration overlap flag exists.
    assert any("NEW1" in f.descriptor for f in brief.concentration)
    # discipline scorecard wired through.
    assert brief.scorecard.discipline_reduce_down_rate == 0.58


def test_execute_is_deterministic() -> None:
    # Two INDEPENDENT instances (not the same uc twice) so the test catches any
    # cross-instance ordering variance, not just re-entrant stability.
    holdings = [Holding("AAPL", 10, 1000, "TFSA"), Holding("RIVN", 5, 500, "Margin")]
    kwargs = dict(
        universe=["AAPL", "NEW1"],
        holdings=holdings,
        as_of=datetime(2026, 6, 8),
        report_dir="data/reports/",
        top_n=10,
    )
    b1 = _make_uc().execute(**kwargs)  # type: ignore[arg-type]
    b2 = _make_uc().execute(**kwargs)  # type: ignore[arg-type]
    assert to_markdown(b1) == to_markdown(b2)
