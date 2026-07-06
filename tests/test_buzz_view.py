"""Contract tests for buzz_view — attention/volume panel (spec D12, ADR-044).

These tests are the binding contract — buzz_view.py must satisfy all five.
"""

import inspect
from types import SimpleNamespace

from adapters.visualization.tabs.stock_analysis import buzz_view
from domain.fit import FORBIDDEN_WORDS


def _sig(source: str, n: int, s: float) -> SimpleNamespace:
    return SimpleNamespace(
        source=source, mention_count=n, sentiment_raw=s, fetched_at="2026-06-27"
    )


def _result(buzz: list[SimpleNamespace] | None = None) -> SimpleNamespace:
    return SimpleNamespace(
        buzz_signals=(
            buzz
            if buzz is not None
            else [_sig("reddit", 30, 0.3), _sig("stocktwits", 12, 0.1)]
        ),
        ticker="NVDA",
    )


def test_total_and_sources() -> None:
    v = buzz_view.build_buzz_view(_result())
    tot = next(m for m in v["metrics"] if "ention" in m.label)
    assert "42" in tot.value  # 30+12


def test_adr044_caveat_present() -> None:
    html = buzz_view.build_buzz_panel(_result())
    assert "ADR-044" in html or "falsified" in html.lower()


def test_empty_buzz_degrades() -> None:
    html = buzz_view.build_buzz_panel(_result(buzz=[]))
    assert "Buzz" in html


def test_panel_renders() -> None:
    assert "Buzz" in buzz_view.build_buzz_panel(_result())


def test_mention_volume_chart_renders_with_multiple_distinct_days() -> None:
    # buzz_signals are loaded from SQLite across every past harvest run, so
    # real tickers often DO have 2+ distinct fetched_at days even though a
    # single run only ever sees "today" -- the trend slot should use them
    # instead of a permanent "not wired" placeholder.
    buzz = [
        _sig("yahoo_finance", 1, 0.1),
        SimpleNamespace(
            source="yahoo_finance",
            mention_count=1,
            sentiment_raw=0.1,
            fetched_at="2026-06-03",
        ),
        SimpleNamespace(
            source="yahoo_finance",
            mention_count=1,
            sentiment_raw=0.1,
            fetched_at="2026-06-04",
        ),
    ]
    html = buzz_view.build_buzz_panel(_result(buzz=buzz))
    assert "mention-volume trend not wired" not in html
    assert "Mentions by day" in html


def test_mention_volume_datagap_with_single_day() -> None:
    # default fixture signals are all dated "2026-06-27" -- only one distinct day
    html = buzz_view.build_buzz_panel(_result())
    assert "data gap" in html.split("Mentions by day")[1][:200]


def test_verdict_mentions_data_gap_only_when_single_day() -> None:
    v_gap = buzz_view.build_buzz_view(_result())
    assert any(
        "not wired" in vv.text and "data gap" in vv.text for vv in v_gap["verdicts"]
    )

    buzz = [
        _sig("yahoo_finance", 1, 0.1),
        SimpleNamespace(
            source="yahoo_finance",
            mention_count=1,
            sentiment_raw=0.1,
            fetched_at="2026-06-03",
        ),
    ]
    v_have = buzz_view.build_buzz_view(_result(buzz=buzz))
    trend_verdict = v_have["verdicts"][0]
    assert "not wired" not in trend_verdict.text.lower()
    assert "recorded day" in trend_verdict.text.lower()


def test_no_streamlit_and_clean() -> None:
    src = inspect.getsource(buzz_view)
    assert "import streamlit" not in src
    low = src.lower()
    for w in FORBIDDEN_WORDS:
        assert w not in low
