import inspect

from adapters.visualization.components import metric_tile
from domain.fit import FORBIDDEN_WORDS


def test_renders_label_value_sub_tone():
    html = metric_tile.render_metric_tile("P/E ttm", "52x", sub="78th", tone="amber")
    assert "P/E ttm" in html and "52x" in html and "78th" in html
    assert "sa-tile t-amber" in html


def test_optional_info_and_viz():
    html = metric_tile.render_metric_tile(
        "Rev YoY",
        "+69%",
        tone="green",
        viz='<svg data-test="spark"></svg>',
        info_meaning="Revenue vs year ago.",
        info_basis="info.revenueGrowth",
    )
    assert 'data-test="spark"' in html
    assert "Revenue vs year ago." in html and "info.revenueGrowth" in html


def test_no_streamlit_and_clean():
    src = inspect.getsource(metric_tile)
    assert "import streamlit" not in src
    low = src.lower()
    for w in FORBIDDEN_WORDS:
        assert w not in low
