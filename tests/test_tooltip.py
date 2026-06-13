from adapters.visualization.components import glossary as g
from adapters.visualization.components.tooltip import tooltip


def test_tooltip_wraps_known_term_with_definition():
    html = tooltip("Beta")
    assert "Beta" in html
    assert g.GLOSSARY["Beta"] in html
    assert "ri-tip" in html  # the cloud span class


def test_tooltip_unknown_term_raises():
    import pytest

    with pytest.raises(KeyError):
        tooltip("NotARealTerm")


def test_tooltip_label_override_keeps_definition():
    html = tooltip("Beta", label="Net β")
    assert "Net β" in html
    assert g.GLOSSARY["Beta"] in html
