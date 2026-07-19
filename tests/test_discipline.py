def test_conditional_vol_signal_zero_when_trend_healthy():
    from domain.discipline import conditional_vol_signal

    assert (
        conditional_vol_signal(recent_vol=0.04, baseline_vol=0.02, trend_health=1.5)
        == 0.0
    )


def test_conditional_vol_signal_zero_when_vol_not_elevated():
    from domain.discipline import conditional_vol_signal

    assert (
        conditional_vol_signal(recent_vol=0.01, baseline_vol=0.02, trend_health=-1.0)
        == 0.0
    )


def test_conditional_vol_signal_positive_when_vol_up_and_trend_down():
    from domain.discipline import conditional_vol_signal

    sig = conditional_vol_signal(recent_vol=0.04, baseline_vol=0.02, trend_health=-1.0)
    assert 0.0 < sig <= 1.0


def test_risk_asymmetry_fields():
    from domain.discipline import risk_asymmetry

    out = risk_asymmetry(price=100.0, trailing_stop=90.0, recent_high=130.0)
    assert abs(out["downside_to_stop"] - 0.10) < 1e-9
    assert abs(out["upside_to_recover"] - 0.30) < 1e-9


def test_disposition_risk_broken_trend_at_loss():
    from domain.discipline import is_disposition_risk

    assert is_disposition_risk(trend_health=-2.0, unrealized_pct=-0.30) is True
    assert is_disposition_risk(trend_health=1.0, unrealized_pct=-0.30) is False
    assert is_disposition_risk(trend_health=-2.0, unrealized_pct=0.50) is False


def test_winner_past_stop():
    from domain.discipline import is_winner_past_stop

    assert is_winner_past_stop(trend_health=1.5, price=95.0, trailing_stop=96.0) is True
    assert (
        is_winner_past_stop(trend_health=1.5, price=100.0, trailing_stop=96.0) is False
    )
    assert (
        is_winner_past_stop(trend_health=-1.0, price=95.0, trailing_stop=96.0) is False
    )


def test_grade_reduce_when_broken_trend_loss_and_market_ok():
    from domain.discipline import Verdict, grade_position

    v, conf, abstained = grade_position(
        trend_health=-3.0,
        vol_signal=0.5,
        relative_strength=-0.2,
        disposition=True,
        winner_past_stop=False,
        market_trend_health=1.0,
    )
    assert v == Verdict.REDUCE
    assert abstained is False
    assert 0.0 < conf <= 1.0


def test_grade_abstains_to_review_when_market_also_broken():
    from domain.discipline import Verdict, grade_position

    v, conf, abstained = grade_position(
        trend_health=-3.0,
        vol_signal=0.5,
        relative_strength=0.1,
        disposition=True,
        winner_past_stop=False,
        market_trend_health=-2.5,
    )
    assert v == Verdict.REVIEW
    assert abstained is True


def test_grade_trim_for_winner_past_stop():
    from domain.discipline import Verdict, grade_position

    v, conf, abstained = grade_position(
        trend_health=1.2,
        vol_signal=0.0,
        relative_strength=0.1,
        disposition=False,
        winner_past_stop=True,
        market_trend_health=1.0,
    )
    assert v == Verdict.TRIM


def test_grade_hold_when_in_trend():
    from domain.discipline import Verdict, grade_position

    v, conf, abstained = grade_position(
        trend_health=2.5,
        vol_signal=0.0,
        relative_strength=0.3,
        disposition=False,
        winner_past_stop=False,
        market_trend_health=1.0,
    )
    assert v in (Verdict.HOLD, Verdict.ADD_OK)


def test_grade_review_when_trend_health_none():
    from domain.discipline import Verdict, grade_position

    v, conf, abstained = grade_position(
        trend_health=None,
        vol_signal=0.0,
        relative_strength=None,
        disposition=False,
        winner_past_stop=False,
        market_trend_health=None,
    )
    assert v == Verdict.REVIEW
    assert abstained is True


# ── FIX 3: verdict rubric ────────────────────────────────────────────────────


def test_verdict_rubric_lines_returns_five_entries() -> None:
    """verdict_rubric_lines() must return exactly 5 entries, one per Verdict."""
    from domain.discipline import Verdict, verdict_rubric_lines

    lines = verdict_rubric_lines()
    assert len(lines) == 5, f"expected 5 rubric entries, got {len(lines)}"
    # All 5 verdict values must be covered
    covered = {label for label, _ in lines}
    for v in Verdict:
        assert v.value in covered, f"Verdict {v.value} missing from rubric"


def test_verdict_rubric_lines_no_forbidden_words() -> None:
    """Rubric text must not contain any forbidden words."""
    from domain.discipline import verdict_rubric_lines
    from domain.fit import FORBIDDEN_WORDS

    lines = verdict_rubric_lines()
    for label, text in lines:
        combined = (label + " " + text).lower()
        for w in FORBIDDEN_WORDS:
            assert (
                w not in combined
            ), f"forbidden word {w!r} in rubric entry ({label!r})"


def test_rubric_html_marks_current_verdict() -> None:
    """render_verdict_rubric_block() must contain all 5 verdict names.

    Formerly this rubric rendered per-ticker via _rubric_html(current_verdict),
    highlighting the fired verdict's row. It's now a single once-per-tab block
    (render_verdict_rubric_block, no per-verdict highlighting) — see
    decision_card.py and tests/components/test_decision_card.py.
    """
    from adapters.visualization.components.decision_card import (
        render_verdict_rubric_block,
    )
    from domain.discipline import Verdict

    html = render_verdict_rubric_block()
    for v in Verdict:
        assert v.value in html, f"verdict {v.value} missing from rubric HTML"


def test_expanded_card_includes_rubric() -> None:
    """render_expanded_card must include a rubric pointer, not the full rubric.

    The full 5-row rubric moved to render_verdict_rubric_block(), rendered
    once per tab instead of once per ticker — the per-ticker card now shows
    only a one-line pointer naming the fired verdict.
    """
    from adapters.visualization.components.decision_card import render_expanded_card
    from application.evidence_card import EvidenceCard
    from domain.discipline import Verdict
    from domain.evidence_rag import RagColor, RagSignal

    sigs = (RagSignal("Technicals", RagColor.GREEN, "above trend"),)
    card = EvidenceCard(ticker="AAPL", signals=sigs, sparkline=())
    html = render_expanded_card(
        card,
        case=None,
        verdict=Verdict.REDUCE,
        name="Apple",
        unrealized_pct=-5.0,
        means="Trend broken.",
        price=150.0,
        cost=180.0,
        returns=(1.0, 2.0, 3.0, 4.0, 5.0),
        reliability="n/a",
    )
    assert (
        "how verdicts are decided" in html.lower()
    )  # pointer to the once-per-tab block
    assert "REDUCE" in html  # fired verdict named in the pointer


def test_expanded_card_shows_cad_symbol_for_tsx_ticker() -> None:
    """A TSX-suffixed ticker's price/cost must show C$, not a bare $ — the real
    caller (portfolio_detail.py) passes the ticker itself as `name`."""
    from adapters.visualization.components.decision_card import render_expanded_card
    from application.evidence_card import EvidenceCard
    from domain.discipline import Verdict
    from domain.evidence_rag import RagColor, RagSignal

    sigs = (RagSignal("Technicals", RagColor.GREEN, "above trend"),)
    card = EvidenceCard(ticker="RY.TO", signals=sigs, sparkline=())
    html = render_expanded_card(
        card,
        case=None,
        verdict=Verdict.HOLD,
        name="RY.TO",
        unrealized_pct=2.0,
        means="Trend intact.",
        price=150.0,
        cost=140.0,
        returns=(1.0, 2.0, 3.0, 4.0, 5.0),
        reliability="n/a",
    )
    assert "C$150.00" in html
    assert "C$140.00" in html
    assert "$150.00" not in html.replace("C$150.00", "")
