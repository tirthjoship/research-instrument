"""Dossier render tests — verify E1/E2/E3/E5 sections render with a fixture payload.

These tests cover the populated path that the screenshotter cannot capture
(it cannot type a ticker in headless mode). They assert:
  - Each render helper does not raise with a fully-populated AnalysisResult.
  - Rendered source contains no FORBIDDEN_WORDS.
  - E1 peer percentiles are surfaced (including DATA_GAP path).
  - E2 analyst panel attribution text is present and correct.
  - E3 news context label is "context, not signal".
  - E5 falsification badge text is present.
  - Trend filter axis key is "Trend filter" (not bare "Trend").
"""

from __future__ import annotations

import inspect

# ---------------------------------------------------------------------------
# Shared fixtures
# ---------------------------------------------------------------------------


def _make_analysis_result(
    with_analyst_panel: bool = True,
    with_news_context: bool = True,
    with_peer_percentiles: bool = True,
) -> object:  # AnalysisResult resolved inside function to avoid top-level import
    """Build a minimal but fully-populated AnalysisResult for render tests."""
    from adapters.visualization.stock_analyzer import AnalysisResult, SectionScore
    from application.analyst_panel import build_analyst_panel
    from application.news_context import build_news_context

    section = SectionScore(
        title="Test",
        score=3,
        max_score=6,
        summary="Test summary.",
        verdicts=[("pass", "all good")],
    )

    analyst_panel = None
    if with_analyst_panel:
        info: dict[str, object] = {
            "analyst_count": 12,
            "analyst_recommendation_mean": 2.2,
            "targetMeanPrice": 550.0,
            "targetHighPrice": 620.0,
            "targetLowPrice": 490.0,
        }
        analyst_panel = build_analyst_panel(info, "2026-06-13")

    news_context = None
    if with_news_context:
        signals = [
            {
                "source": "reuters_rss",
                "title": "NVDA Q1 beats estimates",
                "date": "2026-06-10",
            },
            {
                "source": "reddit_wsb",
                "title": "NVDA momentum discussion",
                "date": "2026-06-09",
            },
        ]
        news_context = build_news_context(signals, 10)

    peer_percentiles: dict[str, float | None] = {}
    if with_peer_percentiles:
        peer_percentiles = {"P/E": 72.5, "Market Cap": 95.0}

    return AnalysisResult(
        ticker="NVDA",
        company_name="NVIDIA Corporation",
        current_price=850.0,
        change_pct=1.5,
        market_cap=2.1e12,
        sector="Technology",
        grade="hold",
        conviction=7.5,
        hold_duration="Monitor daily",
        analyst_count=12,
        analyst_mean_target=550.0,
        analyst_recommendation="Hold",
        valuation=section,
        growth=section,
        performance=section,
        health=section,
        ownership=section,
        sentiment=section,
        supply_chain=None,
        analyst_panel=analyst_panel,
        news_context=news_context,
        peer_percentiles=peer_percentiles,
    )


# ---------------------------------------------------------------------------
# E2: Analyst panel render
# ---------------------------------------------------------------------------


def test_render_analyst_panel_no_raise() -> None:
    """_render_analyst_panel must not raise with a populated result."""
    from adapters.visualization.tabs.stock_analysis import _render_analyst_panel

    result = _make_analysis_result()
    _render_analyst_panel(result)  # should not raise


def test_render_analyst_panel_data_gap_no_raise() -> None:
    """_render_analyst_panel must not raise when panel.data_gap is True."""
    from adapters.visualization.tabs.stock_analysis import _render_analyst_panel
    from application.analyst_panel import build_analyst_panel

    result = _make_analysis_result(with_analyst_panel=False)
    # Build a panel with count=0 -> data_gap=True
    panel = build_analyst_panel({}, "2026-06-13")
    result.analyst_panel = panel
    _render_analyst_panel(result)


def test_analyst_panel_attribution_is_the_street() -> None:
    """Analyst panel attribution must reference 'The Street'."""
    from application.analyst_panel import build_analyst_panel

    panel = build_analyst_panel(
        {"analyst_count": 10, "targetMeanPrice": 500.0}, "2026-06-13"
    )
    assert "The Street" in panel.attribution


def test_render_analyst_panel_source_no_forbidden_words() -> None:
    """_render_analyst_panel source must be free of FORBIDDEN_WORDS."""
    from adapters.visualization.tabs import stock_analysis
    from domain.fit import FORBIDDEN_WORDS

    src = inspect.getsource(stock_analysis._render_analyst_panel).lower()
    for word in FORBIDDEN_WORDS:
        assert word not in src, f"forbidden word {word!r} in _render_analyst_panel"


# ---------------------------------------------------------------------------
# E3: News context render
# ---------------------------------------------------------------------------


def test_render_news_context_no_raise() -> None:
    """_render_news_context must not raise with a populated result."""
    from adapters.visualization.tabs.stock_analysis import _render_news_context

    result = _make_analysis_result()
    _render_news_context(result)


def test_render_news_context_data_gap_no_raise() -> None:
    """_render_news_context must not raise when context.data_gap is True."""
    from adapters.visualization.tabs.stock_analysis import _render_news_context
    from application.news_context import build_news_context

    result = _make_analysis_result(with_news_context=False)
    result.news_context = build_news_context([], 10)  # empty -> data_gap
    _render_news_context(result)


def test_news_context_label_is_correct() -> None:
    """NewsContext.label must be 'context, not signal'."""
    from application.news_context import build_news_context

    ctx = build_news_context(
        [{"source": "reuters", "title": "test", "date": "2026-06-10"}], 10
    )
    assert ctx.label == "context, not signal"


def test_render_news_context_source_no_forbidden_words() -> None:
    """_render_news_context source must be free of FORBIDDEN_WORDS."""
    from adapters.visualization.tabs import stock_analysis
    from domain.fit import FORBIDDEN_WORDS

    src = inspect.getsource(stock_analysis._render_news_context).lower()
    for word in FORBIDDEN_WORDS:
        assert word not in src, f"forbidden word {word!r} in _render_news_context"


# ---------------------------------------------------------------------------
# E1: Peer percentiles render
# ---------------------------------------------------------------------------


def test_render_peer_percentiles_no_raise() -> None:
    """_render_peer_percentiles must not raise with a populated result."""
    from adapters.visualization.tabs.stock_analysis import _render_peer_percentiles

    result = _make_analysis_result()
    _render_peer_percentiles(result)


def test_render_peer_percentiles_data_gap_no_raise() -> None:
    """_render_peer_percentiles must not raise when all percentiles are None."""
    from adapters.visualization.tabs.stock_analysis import _render_peer_percentiles

    result = _make_analysis_result()
    result.peer_percentiles = {"P/E": None, "Market Cap": None}
    _render_peer_percentiles(result)


def test_render_peer_percentiles_source_no_forbidden_words() -> None:
    """_render_peer_percentiles source must be free of FORBIDDEN_WORDS."""
    from adapters.visualization.tabs import stock_analysis
    from domain.fit import FORBIDDEN_WORDS

    src = inspect.getsource(stock_analysis._render_peer_percentiles).lower()
    for word in FORBIDDEN_WORDS:
        assert word not in src, f"forbidden word {word!r} in _render_peer_percentiles"


# ---------------------------------------------------------------------------
# E5: Falsification badge in fit card
# ---------------------------------------------------------------------------


def test_render_fit_card_has_falsification_badge() -> None:
    """_render_fit_card must include falsification reference text."""
    from adapters.visualization.tabs.stock_analysis import _render_fit_card
    from domain.fit import FitFlag, FitVerdict

    verdict = FitVerdict(
        ticker="NVDA",
        evidence_grade="STRONG",
        fit_flags=(FitFlag("BETA_AMPLIFY", "deepens the market bet", "WARNING"),),
        summary="NVDA sits in the top fifth of the screened universe.",
    )
    # Must not raise — badge is rendered as markdown, no return value to assert.
    # If a KeyError or AttributeError were raised, the test would fail.
    _render_fit_card(verdict)


def test_render_fit_card_source_has_falsification_text() -> None:
    """_render_fit_card source must contain the falsification badge text."""
    from adapters.visualization.tabs import stock_analysis

    src = inspect.getsource(stock_analysis._render_fit_card)
    assert (
        "falsified" in src.lower()
    ), "falsification badge missing from _render_fit_card"
    assert (
        "Trust" in src
    ), "Trust tab link missing from _render_fit_card falsification badge"


# ---------------------------------------------------------------------------
# Trend filter axis label
# ---------------------------------------------------------------------------


def test_snowflake_axes_uses_trend_filter_label(monkeypatch, tmp_path) -> None:  # type: ignore[no-untyped-def]
    """_snowflake_axes must return 'Trend filter' key, not bare 'Trend'."""
    import json

    from adapters.visualization.tabs import stock_analysis
    from domain.fit import FitVerdict

    monkeypatch.chdir(tmp_path)
    reports = tmp_path / "data" / "reports"
    reports.mkdir(parents=True)
    (reports / "screen_2026-06-13.json").write_text(
        json.dumps(
            {
                "as_of": "2026-06-13",
                "candidates": [
                    {
                        "ticker": "NVDA",
                        "composite": 0.9,
                        "trend_health": 0.6,
                        "factor_scores": [
                            {"name": "value", "percentile": 0.7},
                            {"name": "quality", "percentile": 0.8},
                            {"name": "momentum", "percentile": 0.6},
                        ],
                    }
                ],
            }
        )
    )
    fit = FitVerdict(ticker="NVDA", evidence_grade="STRONG", fit_flags=(), summary="s.")
    axes = stock_analysis._snowflake_axes(fit)
    assert "Trend filter" in axes, "axis key must be 'Trend filter', not 'Trend'"
    assert "Trend" not in axes  # no bare 'Trend' key remains


# ---------------------------------------------------------------------------
# Whole new-copy vocab guard (E1/E2/E3 sections)
# ---------------------------------------------------------------------------


def test_dossier_sections_source_has_no_forbidden_words() -> None:
    """All new dossier helper sources must be free of FORBIDDEN_WORDS."""
    from adapters.visualization.tabs import stock_analysis
    from domain.fit import FORBIDDEN_WORDS

    helpers = [
        stock_analysis._render_analyst_panel,
        stock_analysis._render_news_context,
        stock_analysis._render_peer_percentiles,
    ]
    for fn in helpers:
        src = inspect.getsource(fn).lower()
        for word in FORBIDDEN_WORDS:
            assert word not in src, f"forbidden word {word!r} found in {fn.__name__}"
