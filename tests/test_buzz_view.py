"""Contract tests for buzz_view — attention/volume panel (spec D12, ADR-044).

These tests are the binding contract — buzz_view.py must satisfy all five.
"""

import inspect
from types import SimpleNamespace

from adapters.visualization.tabs.stock_analysis import buzz_view
from application.news_context import NewsContext, NewsItem
from domain.fit import FORBIDDEN_WORDS


def _sig(
    source: str, n: int, s: float, fetched_at: str = "2026-06-27"
) -> SimpleNamespace:
    return SimpleNamespace(
        source=source, mention_count=n, sentiment_raw=s, fetched_at=fetched_at
    )


def _result(
    buzz: list[SimpleNamespace] | None = None,
    *,
    news_context: NewsContext | None = None,
) -> SimpleNamespace:
    return SimpleNamespace(
        buzz_signals=(
            buzz
            if buzz is not None
            else [_sig("reddit", 30, 0.3), _sig("stocktwits", 12, 0.1)]
        ),
        ticker="NVDA",
        analyst_panel=SimpleNamespace(as_of="2026-06-27"),
        news_context=news_context,
    )


def test_total_and_sources() -> None:
    v = buzz_view.build_buzz_view(_result())
    mentions = next(m for m in v["metrics"] if m.label == "Mentions")
    sources = next(m for m in v["metrics"] if m.label == "Sources")
    assert mentions.value == "42"
    assert sources.value == "2"


def test_empty_buzz_shows_zero_fallbacks() -> None:
    v = buzz_view.build_buzz_view(_result(buzz=[]))
    mentions = next(m for m in v["metrics"] if m.label == "Mentions")
    sources = next(m for m in v["metrics"] if m.label == "Sources")
    news_soc = next(m for m in v["metrics"] if m.label == "News/soc")
    assert mentions.value == "0"
    assert sources.value == "0"
    assert news_soc.value == "0/0"


def test_baseline_multiple_when_two_days() -> None:
    buzz = [
        _sig("yahoo_finance", 2, 0.1, "2026-06-03"),
        _sig("yahoo_finance", 8, 0.1, "2026-06-04"),
    ]
    v = buzz_view.build_buzz_view(_result(buzz=buzz))
    vs_base = next(m for m in v["metrics"] if m.label == "vs base")
    assert vs_base.value == "4.0×"
    assert "ELEVATED" in v["chips"]


def test_vs_base_dash_when_single_day() -> None:
    v = buzz_view.build_buzz_view(_result())
    vs_base = next(m for m in v["metrics"] if m.label == "vs base")
    assert vs_base.value == "—"


def test_news_social_split() -> None:
    buzz = [_sig("reuters_rss", 28, 0.2), _sig("reddit_wsb", 19, 0.1)]
    v = buzz_view.build_buzz_view(_result(buzz=buzz))
    news_soc = next(m for m in v["metrics"] if m.label == "News/soc")
    assert news_soc.value == "28/19"


def test_claim_headline_elevated_when_spike() -> None:
    buzz = [
        _sig("yahoo_finance", 2, 0.1, "2026-06-03"),
        _sig("yahoo_finance", 10, 0.1, "2026-06-04"),
    ]
    v = buzz_view.build_buzz_view(_result(buzz=buzz))
    assert "Loud right now" in v["claim"]


def test_adr044_caveat_present() -> None:
    html = buzz_view.build_buzz_panel(_result())
    assert "ADR-044" in html or "falsified" in html.lower()


def test_empty_buzz_degrades() -> None:
    html = buzz_view.build_buzz_panel(_result(buzz=[]))
    assert "Buzz" in html
    assert "0 mentions" in html


def test_panel_renders() -> None:
    assert "Buzz" in buzz_view.build_buzz_panel(_result())


def test_volume_chart_renders_with_multiple_distinct_days() -> None:
    buzz = [
        _sig("yahoo_finance", 1, 0.1, "2026-05-30"),
        _sig("yahoo_finance", 1, 0.1, "2026-06-03"),
        _sig("yahoo_finance", 5, 0.1, "2026-06-04"),
    ]
    html = buzz_view.build_buzz_panel(_result(buzz=buzz))
    assert "Mention volume," in html
    assert "harvest window" in html
    assert "<rect" in html
    assert ">0</text>" in html


def test_volume_chart_14_day_window_has_zero_stubs() -> None:
    rows = buzz_view._daily_window_series(
        {"2026-06-27": 5},
        buzz_view._parse_fetched_at("2026-06-27"),  # type: ignore[arg-type]
    )
    assert len(rows) == buzz_view.VOLUME_CHART_DAYS
    assert sum(v for _, v, _ in rows) == 5.0


def test_volume_bars_have_axes_and_hover_tooltips() -> None:
    from adapters.visualization.components import panel_charts

    html = panel_charts.volume_bars(
        [("06-04", 16.0, "2026-06-04")], css_class="sa-buzz-vol"
    )
    assert "sa-buzz-bar" in html
    assert "<title>" in html
    assert "2026-06-04: 16 mentions" in html
    assert ">0</text>" in html
    assert ">16</text>" in html
    assert ">06-04</text>" in html
    assert "sa-buzz-bar-tip" in html


def test_focus_volume_rows_trims_sparse_window() -> None:
    rows = [(f"06-{d:02d}", float(d == 4), f"2026-06-{d:02d}") for d in range(1, 15)]
    rows[3] = ("06-04", 8.0, "2026-06-04")
    focused = buzz_view._focus_volume_rows(rows)
    assert len(focused) <= 10
    assert any(v > 0 for _, v, _ in focused)


def test_headlines_link_when_url_present() -> None:
    ctx = NewsContext(
        items=[
            NewsItem(
                "Yahoo Finance",
                "NVDA beats on data center demand",
                "2026-06-26",
                "https://finance.yahoo.com/news/nvda.html",
            ),
        ],
        label="context, not signal",
        data_gap=False,
    )
    html = buzz_view.build_buzz_panel(_result(news_context=ctx))
    assert 'class="sa-buzz-link"' in html
    assert "https://finance.yahoo.com/news/nvda.html" in html
    assert 'target="_blank"' in html


def test_volume_window_anchors_to_latest_harvest_when_ref_is_now() -> None:
    from datetime import datetime, timezone

    buzz = [
        _sig("yahoo_finance", 8, 0.1, "2026-06-03"),
        _sig("yahoo_finance", 9, 0.1, "2026-06-04"),
    ]
    day_totals = buzz_view._day_totals(buzz)
    ref = datetime.now(timezone.utc)
    rows = buzz_view._daily_window_series(day_totals, ref)
    assert sum(1 for _, v, _ in rows if v > 0) >= 2


def test_volume_chart_single_day_uses_focused_window() -> None:
    html = buzz_view.build_buzz_panel(_result())
    assert "Mention volume," in html
    assert "harvest window" in html
    assert "sa-buzz-chart-wrap--sparse" in html
    assert "Single recorded day" not in html


def test_headlines_from_news_context() -> None:
    ctx = NewsContext(
        items=[
            NewsItem(
                "Yahoo Finance",
                f"Headline {i}",
                "2026-06-26",
                f"https://finance.yahoo.com/news/{i}.html",
            )
            for i in range(6)
        ],
        label="context, not signal",
        data_gap=False,
    )
    html = buzz_view.build_buzz_panel(_result(news_context=ctx))
    assert "Recent headlines" in html
    assert html.count("sa-buzz-hl") == 6
    assert "sa-buzz-more" in html
    assert "+ 2 more headlines" in html
    assert "Headline 0" in html
    assert "Headline 5" in html


def test_buzz_panel_balanced_two_column_layout() -> None:
    html = buzz_view.build_buzz_panel(_result())
    assert "sa-buzz-split" in html
    assert "sa-buzz-news-col" in html
    assert "sa-buzz-vol-col" in html
    assert "sa-buzz-chart-wrap" in html
    assert "sa-buzz-vol" in html


def test_buzz_sources_counts_publishers_from_news_context() -> None:
    from application.news_context import NewsContext, NewsItem

    ctx = NewsContext(
        items=[
            NewsItem("Reuters", "Headline A", "2026-07-07"),
            NewsItem("Motley Fool", "Headline B", "2026-07-07"),
            NewsItem("Barrons", "Headline C", "2026-07-07"),
        ],
        label="context, not signal",
        data_gap=False,
    )
    v = buzz_view.build_buzz_view(_result(news_context=ctx))
    sources = next(m for m in v["metrics"] if m.label == "Sources")
    assert sources.value == "3"
    assert sources.sub == "publishers"


def test_headlines_fallback_to_mention_log_without_news() -> None:
    html = buzz_view.build_buzz_panel(_result())
    assert "Recent headlines" in html
    assert "mentions recorded" in html


def test_relative_age_always_days_not_iso() -> None:
    ref = buzz_view._parse_fetched_at("2026-06-27")
    old = buzz_view._parse_fetched_at("2026-05-30")
    assert ref is not None and old is not None
    assert buzz_view._relative_age(old, ref) == "28d"
    assert "2026-" not in buzz_view._relative_age(old, ref)


def test_mention_log_mockup_layout() -> None:
    html = buzz_view.build_buzz_panel(_result())
    assert "Recent headlines" in html
    assert "[Reddit]" in html or "[reddit" in html.lower()


def test_verdict_falsified_not_chart_meta() -> None:
    v = buzz_view.build_buzz_view(_result())
    assert any("falsified" in vv.text.lower() for vv in v["verdicts"])

    buzz = [
        _sig("yahoo_finance", 1, 0.1, "2026-06-03"),
        _sig("yahoo_finance", 4, 0.1, "2026-06-04"),
    ]
    v_have = buzz_view.build_buzz_view(_result(buzz=buzz))
    assert any("spike" in vv.text.lower() for vv in v_have["verdicts"])


def test_no_streamlit_and_clean() -> None:
    src = inspect.getsource(buzz_view)
    assert "import streamlit" not in src
    low = src.lower()
    for w in FORBIDDEN_WORDS:
        assert w not in low
