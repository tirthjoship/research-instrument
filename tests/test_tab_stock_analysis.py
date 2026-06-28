"""Smoke tests for the stock_analysis tab package — SP6 Task 5.

Pure-function tests only: no Streamlit import required.
"""

from __future__ import annotations

from datetime import date
from types import SimpleNamespace
from typing import Any

from adapters.visualization.data_loader import CorroborationTabView
from adapters.visualization.tabs.stock_analysis import (
    _SECTION_LABELS,
    _convergence_badge_html,
)
from adapters.visualization.tabs.stock_analysis.compose import (
    _build_story_banner_html,
    _build_story_phrases,
)
from adapters.visualization.tabs.stock_analysis.market_section import (
    _build_ownership_delta,
    _build_vs_market_card,
    _ownership_delta_html,
    _vs_market_card_html,
)
from adapters.visualization.tabs.stock_analysis.signals_section import (
    _build_sentiment_digest,
    _sentiment_tally_html,
)
from domain.corroboration_models import ConvergenceTier
from tests.fakes.corroboration_store_fake import FAKE_SNAPSHOT


def _buzz(source: str, sentiment: float, mentions: int, date_str: str) -> Any:
    """Minimal BuzzSignal-like object (the builders use getattr)."""
    return SimpleNamespace(
        source=source,
        sentiment_raw=sentiment,
        mention_count=mentions,
        fetched_at=date_str,
    )


def _make_corr_view(snapshot=None):  # type: ignore[no-untyped-def]
    """Build a minimal CorroborationTabView for tests."""
    return CorroborationTabView(
        ticker="AAPL",
        as_of=date(2026, 6, 24),
        claims=(),
        snapshot=snapshot,
        our_readout=None,
        directional_views=(),
    )


# ---------------------------------------------------------------------------
# Section label smoke tests
# ---------------------------------------------------------------------------


def test_section_labels_length() -> None:
    """_SECTION_LABELS must have exactly 5 entries."""
    assert len(_SECTION_LABELS) == 5


def test_section_labels_has_corroboration() -> None:
    """Last entry of _SECTION_LABELS must be 'Corroboration'."""
    assert _SECTION_LABELS[-1] == "Corroboration"


# ---------------------------------------------------------------------------
# Convergence badge pure-function tests
# ---------------------------------------------------------------------------


def test_convergence_badge_html_strong() -> None:
    """STRONG tier badge must contain the green colour #16A34A."""
    html = _convergence_badge_html(ConvergenceTier.STRONG)
    assert "#16A34A" in html
    assert "STRONG" in html


def test_convergence_badge_html_conflicted() -> None:
    """CONFLICTED tier badge must contain the red colour #DC2626."""
    html = _convergence_badge_html(ConvergenceTier.CONFLICTED)
    assert "#DC2626" in html
    assert "CONFLICTED" in html


def test_convergence_badge_html_moderate() -> None:
    """MODERATE tier badge must contain the blue colour #2563EB."""
    html = _convergence_badge_html(ConvergenceTier.MODERATE)
    assert "#2563EB" in html
    assert "MODERATE" in html


def test_convergence_badge_html_weak() -> None:
    """WEAK tier badge must contain the amber colour #CA8A04."""
    html = _convergence_badge_html(ConvergenceTier.WEAK)
    assert "#CA8A04" in html
    assert "WEAK" in html


def test_convergence_badge_html_none_tier() -> None:
    """NONE tier badge must contain the gray colour #94A3B8."""
    html = _convergence_badge_html(ConvergenceTier.NONE)
    assert "#94A3B8" in html
    assert "NONE" in html


# ---------------------------------------------------------------------------
# Badge suppression when snapshot is absent
# ---------------------------------------------------------------------------


def test_convergence_badge_none_when_no_snapshot() -> None:
    """When corr_view.snapshot is None, no badge HTML should be produced."""
    view = _make_corr_view(snapshot=None)
    # Mirrors the guard logic in _render_verdict: badge is empty string when no snapshot.
    badge = ""
    if view is not None and view.snapshot is not None:
        badge = _convergence_badge_html(view.snapshot.convergence)
    assert badge == ""


def test_convergence_badge_present_when_snapshot_provided() -> None:
    """When corr_view.snapshot is set, badge HTML must be non-empty."""
    view = _make_corr_view(snapshot=FAKE_SNAPSHOT)
    badge = ""
    if view is not None and view.snapshot is not None:
        badge = _convergence_badge_html(view.snapshot.convergence)
    assert badge != ""
    # FAKE_SNAPSHOT has ConvergenceTier.MODERATE
    assert "#2563EB" in badge


# ---------------------------------------------------------------------------
# Sentiment digest (signals_section)
# ---------------------------------------------------------------------------


def test_sentiment_digest_none_when_empty() -> None:
    assert _build_sentiment_digest([]) is None


def test_sentiment_digest_tally_and_breakdown() -> None:
    buzz = [
        _buzz("reuters_rss", 0.5, 3, "2026-06-20"),
        _buzz("reuters_rss", -0.4, 2, "2026-06-21"),
        _buzz("reddit_wsb", 0.01, 6, "2026-06-21"),
    ]
    d = _build_sentiment_digest(buzz)
    assert d is not None
    assert d.total_signals == 3
    assert d.total_mentions == 11
    assert (d.positive, d.neutral, d.negative) == (1, 1, 1)
    # Two distinct sources; reddit has the most mentions so sorts first.
    assert set(d.sources) == {"reuters_rss", "reddit_wsb"}
    assert d.source_breakdown[0][0] == "reddit_wsb"
    # Timeline has two dates, ascending.
    assert [date_ for date_, _ in d.timeline] == ["2026-06-20", "2026-06-21"]


def test_sentiment_tally_html_has_falsified_chip() -> None:
    d = _build_sentiment_digest([_buzz("reuters_rss", 0.2, 1, "2026-06-20")])
    assert d is not None
    html = _sentiment_tally_html(d)
    # Evidence chip for the FALSIFIED sentiment signal must be attached.
    assert "FALSIFIED" in html
    assert "ADR-044" in html
    assert "Buzz mix" in html


# ---------------------------------------------------------------------------
# vs-market / technicals card (market_section)
# ---------------------------------------------------------------------------


def test_vs_market_card_computes_excess_and_trend() -> None:
    info = {
        "52WeekChange": 0.30,
        "SandP52WeekChange": 0.10,
        "beta": 1.2,
        "twoHundredDayAverage": 100.0,
        "fiftyDayAverage": 110.0,
    }
    card = _build_vs_market_card(info, current_price=120.0)
    assert card.stock_1y_pct == 30.0
    assert card.spy_1y_pct == 10.0
    assert card.excess_1y_pct == 20.0
    assert card.beta == 1.2
    assert card.price_vs_ma200_pct == 20.0  # (120-100)/100


def test_vs_market_card_html_data_gap() -> None:
    card = _build_vs_market_card({}, current_price=0.0)
    html = _vs_market_card_html(card)
    assert "DATA GAP" in html
    assert "vs Market" in html


# ---------------------------------------------------------------------------
# Ownership QoQ delta (market_section)
# ---------------------------------------------------------------------------


def test_ownership_delta_none_when_empty() -> None:
    assert _build_ownership_delta([]) is None


def test_ownership_delta_net_buyers_and_qoq() -> None:
    quarters = [
        {
            "quarter": "Q1 2026",
            "buys": 1,
            "sells": 2,
            "buy_value": 1e6,
            "sell_value": 3e6,
        },
        {
            "quarter": "Q2 2026",
            "buys": 4,
            "sells": 1,
            "buy_value": 5e6,
            "sell_value": 1e6,
        },
    ]
    delta = _build_ownership_delta(quarters)
    assert delta is not None
    assert delta.latest_quarter == "Q2 2026"
    assert delta.net_value == 4e6  # 5M - 1M
    assert delta.prior_quarter == "Q1 2026"
    assert delta.prior_net_value == -2e6  # 1M - 3M
    assert delta.qoq_delta == 6e6
    html = _ownership_delta_html(delta)
    assert "net buyers" in html
    assert "Q2 2026" in html


# ---------------------------------------------------------------------------
# Story-this-week synthesis banner (compose)
# ---------------------------------------------------------------------------


def test_story_phrases_empty_result() -> None:
    result = SimpleNamespace(
        buzz_signals=[], insider_transactions=[], peer_percentiles={}
    )
    assert _build_story_phrases(result) == []
    assert _build_story_banner_html(result) == ""


def test_story_banner_synthesises_facts() -> None:
    result = SimpleNamespace(
        buzz_signals=[
            _buzz("reuters_rss", 0.5, 2, "2026-06-20"),
            _buzz("reddit_wsb", 0.4, 3, "2026-06-21"),
        ],
        insider_transactions=[
            {"Date": "2026-06-15", "Transaction": "Buy", "Value": 5e6},
        ],
        peer_percentiles={"P/E": 72.0},
    )
    phrases = _build_story_phrases(result)
    joined = " ".join(phrases)
    assert "sentiment" in joined
    assert "insiders net buyers" in joined
    assert "72th percentile" in joined
    html = _build_story_banner_html(result)
    assert "Story this week" in html
    assert "not a forecast" in html
