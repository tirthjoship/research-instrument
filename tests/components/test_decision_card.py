"""Tests for decision_card component (S3)."""

from __future__ import annotations

import inspect

import adapters.visualization.components.decision_card as dc
from adapters.visualization.components import styles
from adapters.visualization.components.decision_card import (
    _sparkline_svg,
    _squares_html,
    render_collapsed_row,
    render_expanded_card,
)
from application.evidence_card import EvidenceCard
from domain.case_models import CaseResult
from domain.discipline import Verdict
from domain.evidence_rag import RagColor, RagSignal
from domain.fit import FORBIDDEN_WORDS


def _card() -> EvidenceCard:
    sigs = (
        RagSignal("Technicals", RagColor.RED, "2.3 ATR below 200-day"),
        RagSignal("Valuation", RagColor.GREEN, "PEG 0.9"),
        RagSignal("Financials", RagColor.GREEN, "FCF positive"),
        RagSignal("Earnings", RagColor.GAP, "DATA-GAP: no earnings history"),
        RagSignal("Analysts", RagColor.AMBER, "43 cover · wide spread"),
    )
    return EvidenceCard(ticker="YUMC", signals=sigs, sparkline=(40.0, 41.0, 44.6))


def test_decision_card_css_present() -> None:
    css = styles.GLOBAL_CSS
    for token in (".dc-row", ".dc-sq", ".dc-sq.gap", ".dc-spark", ".dc-case", ".dc-sk"):
        assert token in css, f"missing CSS class {token}"


def test_squares_html_has_5_with_gap_hatched() -> None:
    html = _squares_html(_card())
    assert html.count("dc-sq") >= 5
    assert "dc-sq gap" in html  # Earnings GAP is hatched
    assert "DATA-GAP: no earnings history" in html
    assert "PEG 0.9" in html  # detail in hover


def test_sparkline_renders_polyline_no_projection() -> None:
    svg = _sparkline_svg((10.0, 11.0, 9.0, 8.0))
    assert "<svg" in svg and "polyline" in svg
    assert "predict" not in svg.lower() and "forecast" not in svg.lower()


def test_sparkline_empty_is_blank_span() -> None:
    assert "dc-spark" in _sparkline_svg(())


def test_collapsed_row_has_verdict_squares_sparkline_pct() -> None:
    html = render_collapsed_row(
        _card(),
        verdict=Verdict.TRIM,
        name="Yum China",
        unrealized_pct=22.7,
        oneliner="Winner pulled back below trend.",
    )
    assert "TRIM" in html and "YUMC" in html and "Yum China" in html
    assert "dc-sq" in html and "dc-spark" in html
    assert "+22.7%" in html
    # honesty: no forbidden verbs in the rendered output text
    for w in ("predict",):
        assert w not in html.lower()


def test_expanded_card_has_table_means_and_case_placeholder() -> None:
    html = render_expanded_card(
        _card(),
        case=None,
        verdict=Verdict.TRIM,
        name="Yum China",
        unrealized_pct=22.7,
        means="A winner dipped — protect gains or give it room?",
        price=44.63,
        cost=36.38,
        returns=(4.1, -4.3, -14.8, -6.9),
        reliability="0 of 231 TRIM calls scored · hit-rate ~mid-July",
    )
    assert "Evidence detail" in html
    assert "DATA-GAP: no earnings history" in html  # GAP row shown honestly
    assert "informs you, not the verdict" in html  # case badge
    assert "Research only" in html  # footer
    assert "not a trade signal" in html


def test_decision_card_no_forbidden_words() -> None:
    src = inspect.getsource(dc).lower()
    for w in FORBIDDEN_WORDS:
        assert w not in src, f"forbidden word {w!r} in decision_card.py"


# ── FIX 1: price/cost formatted to 2 decimal places ─────────────────────────


def test_expanded_card_price_formatted_to_2dp() -> None:
    """render_expanded_card must show price as $XX.XX (2 decimal places)."""
    html = render_expanded_card(
        _card(),
        case=None,
        verdict=Verdict.TRIM,
        name="Yum China",
        unrealized_pct=22.7,
        means="A name dipped — protect gains or give it room?",
        price=44.633,
        cost=36.378,
        returns=(4.1, -4.3, -14.8, -6.9),
        reliability="0 of 231 TRIM calls scored",
    )
    assert "$44.63" in html, "expected '$44.63' in card HTML, got raw float instead"
    assert "$36.38" in html, "expected '$36.38' in card HTML, got raw float instead"
    assert "44.633" not in html, "raw unformatted price leaked into HTML"
    assert "36.378" not in html, "raw unformatted cost leaked into HTML"


def test_expanded_card_price_none_shows_dash() -> None:
    """When price or cost is None the card must show '—' not crash."""
    html = render_expanded_card(
        _card(),
        case=None,
        verdict=Verdict.HOLD,
        name="Yum China",
        unrealized_pct=None,
        means="Stay put.",
        price=None,
        cost=None,
        returns=(),
        reliability="n/a",
    )
    # Both price and cost should show the em-dash placeholder
    assert html.count("—") >= 2


# ---------------------------------------------------------------------------
# Bug fix: the case block must not claim "loads when you open this card"
# (implies still-pending) once a fetch has actually completed with no
# evidence — data_gap=True and case=None (fetch failed) must render the same
# honest "no evidence found" message, distinct from the pending copy.
# ---------------------------------------------------------------------------


def _base_kwargs() -> dict[str, object]:
    return dict(
        verdict=Verdict.TRIM,
        name="Yum China",
        unrealized_pct=22.7,
        means="A winner dipped — protect gains or give it room?",
        price=44.63,
        cost=36.38,
        returns=(4.1, -4.3, -14.8, -6.9),
        reliability="measured forward; see Trust",
    )


def test_case_none_and_data_gap_render_identical_honest_message() -> None:
    """case=None (never fetched / fetch failed) and a data_gap=True CaseResult
    (fetched, no evidence) must render the exact same honest case block —
    no divergent behavior depending on which path produced the empty result."""
    html_none = render_expanded_card(_card(), case=None, **_base_kwargs())
    html_gap = render_expanded_card(
        _card(), case=CaseResult((), (), True), **_base_kwargs()
    )
    assert html_none == html_gap


def test_case_gap_message_does_not_claim_still_pending() -> None:
    """The honest no-evidence message must not read like a pending loader —
    a completed fetch that found nothing is a different state from 'loading'."""
    html = render_expanded_card(
        _card(), case=CaseResult((), (), True), **_base_kwargs()
    )
    assert "loads when you open this card" not in html.lower()
    assert "informs you, not the verdict" in html  # case badge still present
