"""Contract tests for sentiment_view — tone mix + ADR-044 falsified IC (Task 5)."""

import inspect
from types import SimpleNamespace

from adapters.visualization.tabs.stock_analysis import sentiment_view
from domain.fit import FORBIDDEN_WORDS


def _sig(
    s: float,
    *,
    mention_count: int = 5,
    source: str = "yahoo_finance",
    fetched_at: str = "2026-06-27",
) -> SimpleNamespace:
    return SimpleNamespace(
        source=source,
        mention_count=mention_count,
        sentiment_raw=s,
        fetched_at=fetched_at,
    )


def _result(buzz: list | None = None, **kwargs) -> SimpleNamespace:
    return SimpleNamespace(
        buzz_signals=(
            buzz if buzz is not None else [_sig(0.3), _sig(0.4), _sig(-0.2), _sig(0.0)]
        ),
        ticker="NVDA",
        **kwargs,
    )


def test_ic_zero_falsified_crimson() -> None:
    v = sentiment_view.build_sentiment_view(_result())
    ic = next(m for m in v["metrics"] if m.label == "Tested IC")
    assert ic.value == "0.00"
    assert ic.tone == "crimson"
    assert ic.sub == "falsified"


def test_leans_chip_grey_not_green() -> None:
    v = sentiment_view.build_sentiment_view(_result())
    assert "t-green" not in v["chips"]
    assert "LEANS POS" in v["chips"]


def test_all_neutral_shows_neutral_chip_not_leans() -> None:
    buzz = [_sig(0.0), _sig(0.01), _sig(-0.02)]
    v = sentiment_view.build_sentiment_view(_result(buzz=buzz))
    assert "NEUTRAL" in v["chips"]
    assert "LEANS POS" not in v["chips"]
    neu = next(m for m in v["metrics"] if m.label == "Neutral")
    assert neu.value == "100%"


def test_tone_mix_legend_matches_share_tiles() -> None:
    buzz = [_sig(0.0), _sig(0.01), _sig(-0.02)]
    html = sentiment_view.build_sentiment_panel(_result(buzz=buzz))
    assert "Neutral <b>100%</b>" in html
    assert ">17%<" not in html


def test_mockup_metric_labels_and_shares() -> None:
    v = sentiment_view.build_sentiment_view(_result())
    labels = [m.label for m in v["metrics"]]
    assert labels == ["Mean", "Positive", "Neutral", "Negative", "Net", "Tested IC"]
    pos = next(m for m in v["metrics"] if m.label == "Positive")
    assert pos.sub == "share" and pos.value.endswith("%")


def test_mention_weighted_tone() -> None:
    buzz = [
        _sig(0.4, mention_count=10, fetched_at="2026-06-01"),
        _sig(-0.3, mention_count=2, fetched_at="2026-06-02"),
    ]
    v = sentiment_view.build_sentiment_view(_result(buzz=buzz))
    pos = next(m for m in v["metrics"] if m.label == "Positive")
    neg = next(m for m in v["metrics"] if m.label == "Negative")
    assert pos.value == "83%"
    assert neg.value == "17%"


def test_adr044_and_render() -> None:
    panel_html = sentiment_view.build_sentiment_panel(_result())
    assert "Sentiment" in panel_html and (
        "ADR-044" in panel_html or "falsified" in panel_html.lower()
    )
    assert "sa-sentiment-mix" in panel_html
    assert "Tone mix + by source" in panel_html


def test_empty_degrades() -> None:
    assert "Sentiment" in sentiment_view.build_sentiment_panel(_result(buzz=[]))


def test_overlay_gap_reason_is_price_series_when_price_history_missing() -> None:
    html = sentiment_view.build_sentiment_panel(_result())
    assert "no price series available" in html


def test_overlay_gap_reason_is_buzz_sparsity_when_price_history_present() -> None:
    result = SimpleNamespace(
        buzz_signals=[_sig(0.3), _sig(0.4)],
        ticker="NVDA",
        price_history={"closes": [100.0, 101.0, 102.0]},
    )
    html = sentiment_view.build_sentiment_panel(result)
    assert "no price series" not in html
    assert "buzz too sparse to correlate with price" in html


def test_overlay_renders_with_three_distinct_days() -> None:
    buzz = [
        _sig(0.2, fetched_at="2026-06-01"),
        _sig(0.3, fetched_at="2026-06-02"),
        _sig(0.1, fetched_at="2026-06-03"),
    ]
    result = _result(
        buzz=buzz,
        price_history={"closes": [100.0, 101.0, 102.0, 103.0, 104.0]},
    )
    html = sentiment_view.build_sentiment_panel(result)
    assert "stroke-dasharray" in html
    assert "buzz too sparse" not in html
    assert "follows, doesn't lead" in html


def test_overlay_renders_with_two_days_for_live_headlines() -> None:
    from types import SimpleNamespace

    live = [
        SimpleNamespace(
            source="Reuters",
            mention_count=1,
            sentiment_raw=-0.3,
            scorer="keyword_live",
            fetched_at="2026-07-06",
        ),
        SimpleNamespace(
            source="Barrons",
            mention_count=1,
            sentiment_raw=0.2,
            scorer="keyword_live",
            fetched_at="2026-07-07",
        ),
    ]
    result = SimpleNamespace(
        sentiment_signals=live,
        sentiment_from_live=True,
        buzz_signals=[],
        buzz_harvest_stale=False,
        price_history={"closes": [100.0, 101.0, 102.0, 103.0]},
    )
    html = sentiment_view.build_sentiment_panel(result)
    assert "stroke-dasharray" in html
    assert "need 3+" not in html


def test_no_streamlit_and_clean() -> None:
    src = inspect.getsource(sentiment_view)
    assert "import streamlit" not in src
    low = src.lower()
    for w in FORBIDDEN_WORDS:
        assert w not in low, f"FORBIDDEN_WORD {w!r} found in sentiment_view source"
