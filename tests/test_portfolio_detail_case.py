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
