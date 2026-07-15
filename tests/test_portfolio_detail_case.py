"""The shared detail panel must wire the Google-AI case (cache-first, lazy)
and degrade to None on any failure — never crash, never fabricate."""

import adapters.visualization.components.portfolio_detail as pd


def test_resolve_case_returns_none_on_failure(monkeypatch):
    def _boom(*a, **k):
        raise RuntimeError("no network")

    monkeypatch.setattr(pd, "select_case_summarizer", lambda: object())
    monkeypatch.setattr(pd, "get_case_on_expand", _boom)
    assert pd.resolve_case("AAA", object()) is None


def test_resolve_case_passes_through_real_case(monkeypatch):
    sentinel = object()
    monkeypatch.setattr(pd, "select_case_summarizer", lambda: object())
    monkeypatch.setattr(pd, "get_case_on_expand", lambda *a, **k: sentinel)
    assert pd.resolve_case("AAA", object()) is sentinel


def test_resolve_case_threads_real_news_and_extra_facts(monkeypatch):
    """Same fix as Home's _launch_case_fetcher — news=[] gap closed, verdict/why/
    buzz facts threaded through via the shared application.personal_case_facts."""
    captured: dict[str, object] = {}

    def _fake_get_case_on_expand(ticker, card, *, news, expanded, summarizer, extra_facts=(), cache_path=None):  # type: ignore[no-untyped-def]
        captured["news"] = news
        captured["extra_facts"] = extra_facts
        return object()

    monkeypatch.setattr(pd, "select_case_summarizer", lambda: object())
    monkeypatch.setattr(pd, "get_case_on_expand", _fake_get_case_on_expand)
    monkeypatch.setattr(pd, "personal_case_news", lambda ticker: ["real-news"])
    monkeypatch.setattr(
        pd,
        "personal_case_extra_facts",
        lambda ticker, *, verdict, why: (f"Verdict: {verdict}. {why}",),
    )

    pd.resolve_case("AAA", object(), verdict="HOLD", why="steady trend")

    assert captured["news"] == ["real-news"]
    assert captured["extra_facts"] == ("Verdict: HOLD. steady trend",)


def test_resolve_case_threads_reports_dir_into_cache_path(monkeypatch):
    """Portfolio's inspect-detail panel must use the same {reports_dir}-scoped
    cache as Home — the hardcoded data/personal/cited_cases.json default is
    gitignored and never exists on a fresh Cloud clone, so every visitor who
    clicks a holding would otherwise fire a live, uncached Gemini call."""
    captured: dict[str, object] = {}

    def _fake_get_case_on_expand(ticker, card, *, news, expanded, summarizer, extra_facts=(), cache_path=None):  # type: ignore[no-untyped-def]
        captured["cache_path"] = cache_path
        return object()

    monkeypatch.setattr(pd, "select_case_summarizer", lambda: object())
    monkeypatch.setattr(pd, "get_case_on_expand", _fake_get_case_on_expand)
    monkeypatch.setattr(pd, "personal_case_news", lambda ticker: [])
    monkeypatch.setattr(
        pd, "personal_case_extra_facts", lambda ticker, *, verdict, why: ()
    )

    pd.resolve_case("AAA", object(), reports_dir="data/reports/sample")

    assert captured["cache_path"] == "data/reports/sample/home_cited_cases.json"


def test_detail_not_hardcoded_none():
    # guard against the regression we just fixed
    import inspect

    src = inspect.getsource(pd.render_inspect_detail)
    assert "case = None" not in src
    assert "resolve_case" in src


def test_data_gap_case_from_resolve_case_renders_honest_message_not_broken_columns():
    """Portfolio passes resolve_case()'s result straight into render_expanded_card
    with no data_gap collapsing of its own — it relies on the shared component
    (_case_html) to treat data_gap=True honestly instead of rendering empty
    'in its favor' / 'to watch' columns as if it were a real case."""
    from application.evidence_card import EvidenceCard
    from domain.case_models import CaseResult
    from domain.discipline import Verdict

    card = EvidenceCard(ticker="AAA", signals=(), sparkline=())
    html = pd.render_expanded_card(
        card,
        case=CaseResult((), (), True),
        verdict=Verdict.TRIM,
        name="AAA",
        unrealized_pct=1.0,
        means="x",
        price=10.0,
        cost=9.0,
        returns=(),
        reliability="live",
    )
    assert "No cited evidence found" in html
    assert "dc-cols" not in html  # not rendered as an empty two-column case
