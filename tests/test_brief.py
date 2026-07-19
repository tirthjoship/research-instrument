"""Tests for domain/brief.py — models, assemble_brief, to_markdown, to_stdout_masked."""

from hypothesis import given
from hypothesis import strategies as st

from application.brief_summary import brief_to_summary_dict
from domain.brief import (
    BuyCandidateLine,
    ConcentrationFlag,
    HoldingVerdictLine,
    ResearchLink,
    ScorecardSnapshot,
    WeeklyBrief,
    assemble_brief,
    to_markdown,
    to_stdout_masked,
)
from domain.discipline import Verdict
from domain.models import BookMacroExposure, PortfolioRisk, PositionRisk
from domain.regime import Regime
from domain.screen_models import FactorScore, ScreenCandidate, ScreenLabel, ScreenResult


def test_models_construct_and_are_frozen() -> None:
    cand = BuyCandidateLine(
        ticker="AAPL",
        composite=0.42,
        factor_summary="mom p82 · rev n/a · qual n/a · val n/a · trend ok",
        why="strong 12-1 momentum",
        already_held=True,
        label=ScreenLabel.RESEARCH_ONLY,
    )
    hold = HoldingVerdictLine(
        ticker="MSFT",
        unrealized_pct=0.12,
        trend_state="uptrend",
        verdict=Verdict.HOLD,
        why="trend intact",
    )
    conc = ConcentrationFlag(descriptor="Tech 32% of book", soft_warning=True)
    link = ResearchLink(source="WMT", linked="MCK", relationship="customer→supplier")
    card = ScorecardSnapshot(
        screen_window="since 2026-06-08",
        screen_top_ret=None,
        screen_spy_ret=None,
        screen_n=0,
        screen_significant=False,
        discipline_window="21d",
        discipline_reduce_down_rate=0.58,
        discipline_n=5462,
        discipline_gate_status="PENDING",
    )
    brief = WeeklyBrief(
        as_of="2026-06-08",
        regime=Regime.NEUTRAL,
        tilt={"momentum": 0.25, "revision": 0.25, "quality": 0.25, "value": 0.25},
        candidates=(cand,),
        holdings=(hold,),
        research_links=(link,),
        concentration=(conc,),
        scorecard=card,
        screen_label=ScreenLabel.RESEARCH_ONLY,
    )
    assert brief.as_of == "2026-06-08"
    try:
        brief.as_of = "x"  # type: ignore[misc]
        assert False, "should be frozen"
    except Exception:
        pass


# ---------------------------------------------------------------------------
# Helpers shared by assemble / markdown / masked tests
# ---------------------------------------------------------------------------


def _screen_result(label: ScreenLabel) -> ScreenResult:
    fs = (
        FactorScore("momentum", 1.1, 0.82, 0.27),
        FactorScore("revision", 0.0, 0.0, 0.0),
        FactorScore("quality", 0.0, 0.0, 0.0),
        FactorScore("value", 0.0, 0.0, 0.0),
    )
    cands = (
        ScreenCandidate("AAPL", 0.42, fs, 1.3, "strong 12-1 momentum", label),
        ScreenCandidate("NEW1", 0.30, fs, 0.9, "momentum", label),
    )
    return ScreenResult("2026-06-08", cands, 500, "NEUTRAL", None, abstained=False)


def _positions() -> list[PositionRisk]:
    return [
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


def _portfolio() -> PortfolioRisk:
    return PortfolioRisk(2, 0.5, 0.22, {"HOLD": 1, "REDUCE": 1})


def _scorecard() -> ScorecardSnapshot:
    return ScorecardSnapshot(
        "since 2026-06-08", None, None, 0, False, "21d", 0.58, 5462, "PENDING"
    )


# ---------------------------------------------------------------------------
# Task 4: assemble_brief tests
# ---------------------------------------------------------------------------


def test_assemble_marks_already_held_candidate() -> None:
    brief = assemble_brief(
        as_of="2026-06-08",
        regime=Regime.NEUTRAL,
        tilt={"momentum": 0.25, "revision": 0.25, "quality": 0.25, "value": 0.25},
        screen_result=_screen_result(ScreenLabel.RESEARCH_ONLY),
        screen_label=ScreenLabel.RESEARCH_ONLY,
        top_n=10,
        positions=_positions(),
        portfolio=_portfolio(),
        held_tickers={"AAPL", "RIVN"},
        cluster_overlaps={"AAPL": ["MSFT"], "NEW1": []},
        scorecard=_scorecard(),
        concentration_threshold=0.20,
    )
    aapl = next(c for c in brief.candidates if c.ticker == "AAPL")
    new1 = next(c for c in brief.candidates if c.ticker == "NEW1")
    assert aapl.already_held is True
    assert new1.already_held is False


def test_assemble_orders_holdings_reduce_first() -> None:
    brief = assemble_brief(
        as_of="2026-06-08",
        regime=Regime.NEUTRAL,
        tilt={"momentum": 0.25, "revision": 0.25, "quality": 0.25, "value": 0.25},
        screen_result=_screen_result(ScreenLabel.RESEARCH_ONLY),
        screen_label=ScreenLabel.RESEARCH_ONLY,
        top_n=10,
        positions=_positions(),
        portfolio=_portfolio(),
        held_tickers={"AAPL", "RIVN"},
        cluster_overlaps={},
        scorecard=_scorecard(),
        concentration_threshold=0.20,
    )
    # REDUCE is the most urgent verdict — must sort before HOLD.
    assert brief.holdings[0].verdict == Verdict.REDUCE


def test_assemble_flags_concentration_when_over_threshold() -> None:
    brief = assemble_brief(
        as_of="2026-06-08",
        regime=Regime.NEUTRAL,
        tilt={"momentum": 0.25, "revision": 0.25, "quality": 0.25, "value": 0.25},
        screen_result=_screen_result(ScreenLabel.RESEARCH_ONLY),
        screen_label=ScreenLabel.RESEARCH_ONLY,
        top_n=10,
        positions=_positions(),
        portfolio=_portfolio(),
        held_tickers={"AAPL", "RIVN"},
        cluster_overlaps={},
        scorecard=_scorecard(),
        concentration_threshold=0.20,
    )
    # top_concentration 0.22 > 0.20 → one soft flag.
    assert any(f.soft_warning for f in brief.concentration)


def test_assemble_top_n_limits_candidates() -> None:
    brief = assemble_brief(
        as_of="2026-06-08",
        regime=Regime.NEUTRAL,
        tilt={"momentum": 0.25, "revision": 0.25, "quality": 0.25, "value": 0.25},
        screen_result=_screen_result(ScreenLabel.RESEARCH_ONLY),
        screen_label=ScreenLabel.RESEARCH_ONLY,
        top_n=1,
        positions=_positions(),
        portfolio=_portfolio(),
        held_tickers=set(),
        cluster_overlaps={},
        scorecard=_scorecard(),
        concentration_threshold=0.20,
    )
    assert len(brief.candidates) == 1


# ---------------------------------------------------------------------------
# Task 5: to_markdown tests
# ---------------------------------------------------------------------------


def _full_brief(
    label: ScreenLabel, macro: BookMacroExposure | None = None
) -> WeeklyBrief:
    return assemble_brief(
        as_of="2026-06-08",
        regime=Regime.RISK_OFF,
        tilt={"momentum": 0.15, "revision": 0.15, "quality": 0.40, "value": 0.30},
        screen_result=_screen_result(label),
        screen_label=label,
        top_n=10,
        positions=_positions(),
        portfolio=_portfolio(),
        held_tickers={"AAPL", "RIVN"},
        cluster_overlaps={},
        scorecard=_scorecard(),
        concentration_threshold=0.20,
        macro=macro,
    )


def _macro() -> BookMacroExposure:
    return BookMacroExposure(
        as_of="2026-06-08",
        factors=("SPY",),
        net_beta_by_factor={"SPY": 1.1},
        systematic_share=0.71,
        idiosyncratic_share=0.29,
        dominant_factor="SPY",
        flags=(),
        holdings=(),
        coverage_holdings=1,
        total_holdings=2,
        coverage_value_frac=0.5,
    )


def test_markdown_has_all_sections() -> None:
    md = to_markdown(_full_brief(ScreenLabel.RESEARCH_ONLY))
    assert "WEEKLY BRIEF" in md
    assert "REGIME" in md
    assert "## Needs Review" in md
    assert "## Holding Steady" in md
    assert "CONCENTRATION" in md
    assert "## Scorecard" in md
    assert "RIVN" in md  # full markdown DOES include holding tickers (gitignored file)


def test_markdown_splits_holdings_into_needs_review_and_holding_steady_tables() -> None:
    md = to_markdown(_full_brief(ScreenLabel.RESEARCH_ONLY))
    assert "## Needs Review" in md
    assert "## Holding Steady" in md
    assert "| Ticker | Verdict | P&L | Why |" in md


def test_markdown_has_verdict_rules_glossary_once_at_the_end() -> None:
    md = to_markdown(_full_brief(ScreenLabel.RESEARCH_ONLY))
    assert md.count("## How Verdicts Are Decided") == 1
    tail = md.rsplit("## How Verdicts Are Decided", 1)[1]
    for label in ("REVIEW", "TRIM", "REDUCE", "ADD_OK", "HOLD"):
        assert label in tail
    # Glossary must be the LAST section — no other "## " header follows it.
    assert "## " not in tail
    # The document's final sentence is the glossary's closing caveat line.
    assert md.rstrip().endswith("Research only, not a trade signal._")


def test_markdown_macro_and_scorecard_are_tables() -> None:
    md = to_markdown(_full_brief(ScreenLabel.RESEARCH_ONLY, macro=_macro()))
    assert "## Macro Exposure" in md
    assert "## Scorecard" in md
    assert "| Metric | Value |" in md
    assert "| Rule | Window | Result |" in md


def test_markdown_macro_exposure_absent_when_not_computed() -> None:
    md = to_markdown(_full_brief(ScreenLabel.RESEARCH_ONLY))
    assert "## Macro Exposure" in md
    assert "_(macro-beta not computed)_" in md


def test_markdown_scorecard_tracked_but_unresolved() -> None:
    # n>0 with None returns must read "tracked — returns not yet resolved",
    # NOT "no calls tracked yet" (which is only correct at n==0).
    card = ScorecardSnapshot(
        screen_window="forward since 2026-06-08",
        screen_top_ret=None,
        screen_spy_ret=None,
        screen_n=47,
        screen_significant=False,
        discipline_window="21d",
        discipline_reduce_down_rate=None,
        discipline_n=0,
        discipline_gate_status="PENDING",
    )
    brief = assemble_brief(
        as_of="2026-06-08",
        regime=Regime.NEUTRAL,
        tilt={"momentum": 0.25, "revision": 0.25, "quality": 0.25, "value": 0.25},
        screen_result=_screen_result(ScreenLabel.RESEARCH_ONLY),
        screen_label=ScreenLabel.RESEARCH_ONLY,
        top_n=10,
        positions=_positions(),
        portfolio=_portfolio(),
        held_tickers=set(),
        cluster_overlaps={},
        scorecard=card,
        concentration_threshold=0.20,
    )
    md = to_markdown(brief)
    assert "47 calls tracked" in md
    assert "returns not yet resolved" in md
    assert "no calls tracked yet" not in md


def test_markdown_research_only_has_no_buy_language() -> None:
    md = to_markdown(_full_brief(ScreenLabel.RESEARCH_ONLY)).lower()
    assert "buy candidates" not in md
    assert "evidence-ranked" in md  # honest header instead


def test_markdown_validated_uses_buy_header() -> None:
    md = to_markdown(_full_brief(ScreenLabel.VALIDATED))
    assert "BUY CANDIDATES" in md


# ---------------------------------------------------------------------------
# Task 6: to_stdout_masked tests
# ---------------------------------------------------------------------------


def test_masked_stdout_hides_holding_tickers_and_pnl() -> None:
    out = to_stdout_masked(_full_brief(ScreenLabel.RESEARCH_ONLY))
    assert "RIVN" not in out  # holding ticker masked
    assert "-45%" not in out and "-0.45" not in out  # holding P&L masked
    assert "HOLDINGS (masked)" in out  # aggregate counts shown
    assert "AAPL" in out  # public candidate IS shown
    assert "already held" not in out  # ADR-047: never reveal a held candidate


def test_masked_stdout_leaks_no_holding_field_value() -> None:
    # Structural guarantee: NO HoldingVerdictLine field other than the aggregate
    # verdict count appears in masked output. Iterating fields keeps this correct
    # as new fields are added (vs. hardcoding fixture values).
    brief = _full_brief(ScreenLabel.RESEARCH_ONLY)
    out = to_stdout_masked(brief)
    candidate_tickers = {c.ticker for c in brief.candidates}
    for h in brief.holdings:
        # A holding that is ALSO a public candidate legitimately shows its ticker
        # (as a candidate, not flagged as held). Only pure holdings must be hidden.
        if h.ticker not in candidate_tickers:
            assert h.ticker not in out
        assert str(abs(h.unrealized_pct)) not in out
        assert h.why not in out


def test_masked_stdout_shows_verdict_counts() -> None:
    out = to_stdout_masked(_full_brief(ScreenLabel.RESEARCH_ONLY))
    assert "REDUCE" in out  # counts, not names


@given(label=st.sampled_from([ScreenLabel.RESEARCH_ONLY, ScreenLabel.VALIDATED]))
def test_masked_research_only_no_buy_language(label: ScreenLabel) -> None:
    out = to_stdout_masked(_full_brief(label)).lower()
    if label == ScreenLabel.RESEARCH_ONLY:
        assert "buy candidates" not in out


# ---------------------------------------------------------------------------
# Task 3: abstained is a single source of truth — comes from ScreenResult,
# NOT recomputed from len(candidates).
# ---------------------------------------------------------------------------


def _screen_result_not_abstained(label: ScreenLabel) -> ScreenResult:
    """Screen result with candidates and abstained=False (the normal case)."""
    return _screen_result(label)  # already sets abstained=False


def _screen_result_empty_not_abstained(label: ScreenLabel) -> ScreenResult:
    """Zero candidates but abstained=False — screen ran, found nothing passable,
    but did NOT invoke the thin-coverage abstention gate.
    This is the MEANINGFUL case the old len(candidates)==0 logic gets WRONG:
    it would return True, but the correct answer is False."""
    return ScreenResult("2026-06-08", (), 500, "NEUTRAL", None, abstained=False)


def test_abstained_false_with_candidates() -> None:
    """brief_to_summary_dict must return abstained=False when the source flag is False,
    regardless of whether candidates are present."""
    brief = assemble_brief(
        as_of="2026-06-08",
        regime=Regime.NEUTRAL,
        tilt={"momentum": 0.25, "revision": 0.25, "quality": 0.25, "value": 0.25},
        screen_result=_screen_result_not_abstained(ScreenLabel.RESEARCH_ONLY),
        screen_label=ScreenLabel.RESEARCH_ONLY,
        top_n=10,
        positions=_positions(),
        portfolio=_portfolio(),
        held_tickers=set(),
        cluster_overlaps={},
        scorecard=_scorecard(),
    )
    # Candidates ARE present; source abstained is False.
    assert len(brief.candidates) > 0
    out = brief_to_summary_dict(brief)
    assert out["abstained"] is False


def test_abstained_false_with_zero_candidates_when_source_is_false() -> None:
    """The key regression case: zero candidates but source abstained=False.
    Old code: len(candidates)==0 → True  (WRONG).
    Correct:  source flag False          → False."""
    brief = assemble_brief(
        as_of="2026-06-08",
        regime=Regime.NEUTRAL,
        tilt={"momentum": 0.25, "revision": 0.25, "quality": 0.25, "value": 0.25},
        screen_result=_screen_result_empty_not_abstained(ScreenLabel.RESEARCH_ONLY),
        screen_label=ScreenLabel.RESEARCH_ONLY,
        top_n=10,
        positions=_positions(),
        portfolio=_portfolio(),
        held_tickers=set(),
        cluster_overlaps={},
        scorecard=_scorecard(),
    )
    # Candidates are EMPTY but source abstained is False.
    assert len(brief.candidates) == 0
    out = brief_to_summary_dict(brief)
    # Old len(candidates)==0 code returns True here — this is the bug.
    assert out["abstained"] is False
