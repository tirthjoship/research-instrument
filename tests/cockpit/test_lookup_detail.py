import inspect

from tests.cockpit.fake_st import FakeSt


def test_lookup_renders_input_and_batch_path(monkeypatch, tmp_path):
    from adapters.visualization.cockpit import _lookup

    sink: list[str] = []
    monkeypatch.setattr(_lookup, "st", FakeSt(sink))
    _lookup.render(reports_dir=str(tmp_path), summary_path=str(tmp_path / "x.json"))
    out = " ".join(sink)
    assert "Lookup" in out


def test_detail_sections_present(monkeypatch):
    from adapters.visualization.cockpit import stock_detail

    # the drawer body renders fit card + snowflake + facts for a fake verdict
    src = inspect.getsource(stock_detail)
    assert "st.dialog" in src
    assert "_render_fit_card" in src and "_snowflake_axes" in src


def test_stock_detail_keeps_research_only_caveat():
    # Positive guard (replaces the one lost when tabs/stock_analysis.py was deleted):
    # the drawer must keep its "does not forecast returns" caveat, or RESEARCH_ONLY
    # framing silently erodes with no test failing.
    from adapters.visualization.cockpit import stock_detail

    src = inspect.getsource(stock_detail).lower()
    assert "does not forecast returns" in src


def test_stock_detail_source_has_no_forbidden_words():
    from adapters.visualization.cockpit import stock_detail
    from domain.fit import FORBIDDEN_WORDS

    src = inspect.getsource(stock_detail).lower()
    for word in FORBIDDEN_WORDS:
        assert word not in src, f"forbidden word {word!r} in stock_detail source"


def test_lookup_source_has_no_forbidden_words():
    from adapters.visualization.cockpit import _lookup
    from domain.fit import FORBIDDEN_WORDS

    src = inspect.getsource(_lookup).lower()
    for word in FORBIDDEN_WORDS:
        assert word not in src, f"forbidden word {word!r} in _lookup source"
