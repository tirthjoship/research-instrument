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
