import inspect

from adapters.visualization.components import info_tip
from domain.fit import FORBIDDEN_WORDS


def test_renders_meaning_and_basis():
    html = info_tip.render_info("P/E above 78% of peers.", basis="peer_percentiles")
    assert "sa-info" in html and "sa-tip" in html
    assert "P/E above 78% of peers." in html
    assert "sa-tip-basis" in html and "peer_percentiles" in html


def test_basis_optional():
    html = info_tip.render_info("Trailing fact.")
    assert "sa-tip" in html and "sa-tip-basis" not in html


def test_escapes_html():
    html = info_tip.render_info("P/E <ratio> rich")
    assert "<ratio>" not in html and "&lt;ratio&gt;" in html


def test_no_streamlit_and_clean():
    src = inspect.getsource(info_tip)
    assert "import streamlit" not in src
    low = src.lower()
    for w in FORBIDDEN_WORDS:
        assert w not in low
