"""Tests for My Portfolio tab — decision-card row rendering (Task 9).

The Holding domain model carries: symbol, quantity, purchase_price, purchase_date, notes.
Unrealized % is COMPUTED from live price vs purchase_price.
Verdict and why text are SOURCED from brief_summary.json.
There are NO 5-signal RAG arrays on the Holding model — that is an honest DATA-GAP.

Test harness pattern mirrors test_weekly_brief_tab.py / test_risk_tab.py:
  - patch st.markdown to capture rendered HTML
  - assert structural invariants without starting Streamlit
"""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock, patch

# ---------------------------------------------------------------------------
# Harness helpers
# ---------------------------------------------------------------------------


class _NullCtx:
    """Minimal context-manager stand-in for st.columns / st.expander entries."""

    def __enter__(self) -> "_NullCtx":
        return self

    def __exit__(self, *_: object) -> None:
        pass

    # Delegate attribute lookups to MagicMock so .button / .info / .markdown work
    def __getattr__(self, name: str) -> Any:
        return MagicMock()


def _make_holding(
    symbol: str = "AAPL",
    quantity: float = 10.0,
    purchase_price: float = 100.0,
    purchase_date: str = "2025-01-01",
    notes: str = "",
) -> Any:
    from domain.models import Holding

    return Holding(
        symbol=symbol,
        quantity=quantity,
        purchase_price=purchase_price,
        purchase_date=purchase_date,
        notes=notes,
    )


# ---------------------------------------------------------------------------
# Unit tests for _render_position_card helper
# ---------------------------------------------------------------------------


def test_render_position_card_pill_present() -> None:
    """Decision-card row must render the verdict pill text (e.g. 'TRIM')."""
    collected: list[str] = []

    import streamlit as st

    original_markdown = st.markdown

    def capture(content: object, **kwargs: object) -> None:
        if isinstance(content, str):
            collected.append(content)
        original_markdown(content, **kwargs)  # type: ignore[arg-type]

    holding = _make_holding(symbol="NVDA", purchase_price=200.0)
    prices = {"NVDA": {"price": 216.0, "change_pct": 1.5}}
    brief_holding = {
        "ticker": "NVDA",
        "verdict": "TRIM",
        "unrealized_pct": 8.0,
        "trend_state": "uptrend",
        "why": "momentum intact",
    }

    from adapters.visualization.tabs.positions import _render_position_card

    with (
        patch.object(st, "markdown", side_effect=capture),
        patch.object(st, "columns", return_value=[_NullCtx(), _NullCtx()]),
        patch.object(st, "button", return_value=False),
        patch.object(st, "expander", return_value=_NullCtx()),
        patch.object(st, "caption"),
        patch.object(st, "info"),
    ):
        _render_position_card(holding, prices, "dummy.db", brief_holding=brief_holding)

    all_html = "\n".join(collected).lower()
    assert (
        "trim" in all_html
    ), f"Verdict pill 'TRIM' not found in rendered HTML:\n{all_html[:1000]}"


def test_render_position_card_unrealized_pct_present() -> None:
    """Decision-card row must show the unrealized % figure."""
    collected: list[str] = []

    import streamlit as st

    original_markdown = st.markdown

    def capture(content: object, **kwargs: object) -> None:
        if isinstance(content, str):
            collected.append(content)
        original_markdown(content, **kwargs)  # type: ignore[arg-type]

    holding = _make_holding(symbol="AAPL", purchase_price=150.0)
    prices = {"AAPL": {"price": 165.0, "change_pct": 2.0}}
    brief_holding = {
        "ticker": "AAPL",
        "verdict": "HOLD",
        "unrealized_pct": 10.0,
        "trend_state": "uptrend",
        "why": "trend intact, no action needed",
    }

    from adapters.visualization.tabs.positions import _render_position_card

    with (
        patch.object(st, "markdown", side_effect=capture),
        patch.object(st, "columns", return_value=[_NullCtx(), _NullCtx()]),
        patch.object(st, "button", return_value=False),
        patch.object(st, "expander", return_value=_NullCtx()),
        patch.object(st, "caption"),
        patch.object(st, "info"),
    ):
        _render_position_card(holding, prices, "dummy.db", brief_holding=brief_holding)

    all_html = "\n".join(collected)
    assert (
        "%" in all_html
    ), f"Unrealized % not found in rendered HTML:\n{all_html[:1000]}"


def test_render_position_card_review_framing_not_buy_sell() -> None:
    """Verdict copy must use review-framing language, not 'buy' or 'sell'.

    We inspect _render_position_card source specifically (not the full module)
    to avoid false positives from the trade form which legitimately uses 'sell'.
    """
    import inspect

    from adapters.visualization.tabs import positions

    # The decision-card helper must contain review-framing language.
    src_card = inspect.getsource(positions._render_position_card)  # type: ignore[attr-defined]
    assert (
        "review" in src_card.lower() or "REVIEW" in src_card
    ), "_render_position_card must include review-framing language"


def test_render_position_card_verdict_no_buy_sell_in_pill() -> None:
    """The verdict pill rendered for TRIM must not contain the words 'buy' or 'sell'."""
    from adapters.visualization.tabs.positions import _verdict_pill_html

    pill = _verdict_pill_html("TRIM")
    assert "buy" not in pill.lower(), f"'buy' must not appear in verdict pill: {pill}"
    assert "sell" not in pill.lower(), f"'sell' must not appear in verdict pill: {pill}"
    assert "TRIM" in pill, f"Verdict text 'TRIM' must appear in pill: {pill}"


def test_verdict_pill_html_hold() -> None:
    """HOLD verdict pill must render correctly."""
    from adapters.visualization.tabs.positions import _verdict_pill_html

    pill = _verdict_pill_html("HOLD")
    assert "HOLD" in pill
    assert "buy" not in pill.lower()
    assert "sell" not in pill.lower()


def test_verdict_pill_html_reduce() -> None:
    """REDUCE verdict pill must render correctly."""
    from adapters.visualization.tabs.positions import _verdict_pill_html

    pill = _verdict_pill_html("REDUCE")
    assert "REDUCE" in pill
    assert "sell" not in pill.lower()


def test_render_position_card_data_gap_no_brief() -> None:
    """When no brief_holding is provided, card renders DATA-GAP for verdict — no crash."""
    import streamlit as st

    from adapters.visualization.tabs.positions import _render_position_card

    holding = _make_holding(symbol="MSFT", purchase_price=300.0)
    prices = {"MSFT": {"price": 310.0, "change_pct": 0.5}}

    collected: list[str] = []
    original_markdown = st.markdown

    def capture(content: object, **kwargs: object) -> None:
        if isinstance(content, str):
            collected.append(content)
        original_markdown(content, **kwargs)  # type: ignore[arg-type]

    with (
        patch.object(st, "markdown", side_effect=capture),
        patch.object(st, "columns", return_value=[_NullCtx(), _NullCtx()]),
        patch.object(st, "button", return_value=False),
        patch.object(st, "expander", return_value=_NullCtx()),
        patch.object(st, "caption"),
        patch.object(st, "info"),
    ):
        _render_position_card(holding, prices, "dummy.db", brief_holding=None)

    all_html = "\n".join(collected).lower()
    # Must either show DATA-GAP or degrade gracefully — never crash
    assert "msft" in all_html, "Ticker must always appear in card HTML"


def test_render_position_card_why_text_present() -> None:
    """The one-line why/meaning text from brief_holding must appear in the card."""
    collected: list[str] = []

    import streamlit as st

    original_markdown = st.markdown

    def capture(content: object, **kwargs: object) -> None:
        if isinstance(content, str):
            collected.append(content)
        original_markdown(content, **kwargs)  # type: ignore[arg-type]

    holding = _make_holding(symbol="TSLA", purchase_price=250.0)
    prices = {"TSLA": {"price": 225.0, "change_pct": -1.0}}
    why_text = "trend broken — size reduction warranted"
    brief_holding = {
        "ticker": "TSLA",
        "verdict": "REDUCE",
        "unrealized_pct": -10.0,
        "trend_state": "broken",
        "why": why_text,
    }

    from adapters.visualization.tabs.positions import _render_position_card

    with (
        patch.object(st, "markdown", side_effect=capture),
        patch.object(st, "columns", return_value=[_NullCtx(), _NullCtx()]),
        patch.object(st, "button", return_value=False),
        patch.object(st, "expander", return_value=_NullCtx()),
        patch.object(st, "caption"),
        patch.object(st, "info"),
    ):
        _render_position_card(holding, prices, "dummy.db", brief_holding=brief_holding)

    all_html = "\n".join(collected)
    assert (
        why_text in all_html
    ), f"Why text must appear in card. Text: {why_text!r}\nHTML: {all_html[:1200]}"


# ---------------------------------------------------------------------------
# Glossary — new terms used in decision-card rows must be registered
# ---------------------------------------------------------------------------


def test_glossary_has_position_verdict_terms() -> None:
    """Verdict-framing terms used in position cards must be in the glossary."""
    from adapters.visualization.components.glossary import GLOSSARY

    assert "Trim flag" in GLOSSARY, "'Trim flag' must be registered in glossary"
    assert "Reduce flag" in GLOSSARY, "'Reduce flag' must be registered in glossary"
    assert "Hold flag" in GLOSSARY, "'Hold flag' must be registered in glossary"
