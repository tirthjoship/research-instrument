"""Glossary single-source + tooltip helper."""


def test_glossary_has_core_terms():
    from adapters.visualization.components.glossary import GLOSSARY

    for term in (
        "Confidence interval (CI)",
        "Slippage",
        "Tercile",
        "Abnormal return",
        "IC (information coefficient)",
        "Sharpe ratio",
        "Bootstrap",
        "Pre-registration",
        "Look-ahead bias",
    ):
        assert term in GLOSSARY
        assert len(GLOSSARY[term]) > 20  # real definition, not a stub


def test_tip_wraps_text_with_definition():
    from adapters.visualization.components.glossary import tip

    html = tip("Sharpe ratio")
    assert 'class="tip"' in html
    assert "Sharpe ratio" in html
    assert "data-tip=" in html


def test_tip_unknown_term_returns_plain_text():
    from adapters.visualization.components.glossary import tip

    assert tip("Nonsense Term") == "Nonsense Term"


def test_tip_escapes_html_in_definition(monkeypatch):
    from adapters.visualization.components import glossary

    monkeypatch.setitem(glossary.GLOSSARY, "XSS", 'a "quote" and <b>tag</b>')
    out = glossary.tip("XSS")
    assert '"quote"' not in out  # raw double-quotes escaped inside attribute
    assert "<b>" not in out  # raw tag escaped
    assert "&quot;" in out and "&lt;b&gt;" in out
