import inspect

import pytest

from adapters.visualization.components import status_chip
from domain.fit import FORBIDDEN_WORDS


def test_renders_label_value_tone_and_rule():
    html = status_chip.render_status_chip(
        "RICH",
        "P/E 78th",
        tone="amber",
        rule="P/E >=75th pct of peers; price level only, not overvalued/sell",
    )
    assert "RICH" in html and "P/E 78th" in html
    assert "sa-chip t-amber" in html
    assert ">=75th pct" in html  # rule surfaced in tooltip


def test_rule_is_required():
    with pytest.raises(ValueError):
        status_chip.render_status_chip("RICH", "78th", tone="amber", rule="")


def test_invalid_tone_rejected():
    with pytest.raises(ValueError):
        status_chip.render_status_chip("X", "1", tone="rainbow", rule="r")


def test_no_streamlit_and_clean():
    src = inspect.getsource(status_chip)
    assert "import streamlit" not in src
    low = src.lower()
    for w in FORBIDDEN_WORDS:
        assert w not in low
