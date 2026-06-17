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
