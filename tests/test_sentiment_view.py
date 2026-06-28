"""Contract tests for sentiment_view — tone mix + ADR-044 falsified IC (Task 5)."""

import inspect
from types import SimpleNamespace

from adapters.visualization.tabs.stock_analysis import sentiment_view
from domain.fit import FORBIDDEN_WORDS


def _sig(s: float) -> SimpleNamespace:
    return SimpleNamespace(
        source="reddit", mention_count=5, sentiment_raw=s, fetched_at="2026-06-27"
    )


def _result(buzz: list | None = None) -> SimpleNamespace:
    return SimpleNamespace(
        buzz_signals=(
            buzz if buzz is not None else [_sig(0.3), _sig(0.4), _sig(-0.2), _sig(0.0)]
        ),
        ticker="NVDA",
    )


def test_ic_zero_falsified_crimson() -> None:
    v = sentiment_view.build_sentiment_view(_result())
    ic = next(m for m in v["metrics"] if "IC" in m.label)
    assert "0.00" in ic.value or "0" in ic.value
    assert ic.tone == "crimson"


def test_leans_chip_grey_not_green() -> None:
    v = sentiment_view.build_sentiment_view(_result())
    assert "t-green" not in v["chips"]


def test_adr044_and_render() -> None:
    panel_html = sentiment_view.build_sentiment_panel(_result())
    assert "Sentiment" in panel_html and (
        "ADR-044" in panel_html or "falsified" in panel_html.lower()
    )


def test_empty_degrades() -> None:
    assert "Sentiment" in sentiment_view.build_sentiment_panel(_result(buzz=[]))


def test_no_streamlit_and_clean() -> None:
    src = inspect.getsource(sentiment_view)
    assert "import streamlit" not in src
    low = src.lower()
    for w in FORBIDDEN_WORDS:
        assert w not in low, f"FORBIDDEN_WORD {w!r} found in sentiment_view source"
