import inspect

from adapters.visualization.components import funnel
from domain.fit import FORBIDDEN_WORDS


def test_funnel_stages_render_counts():
    html = funnel.render_funnel(
        [("Universe", 512), ("Liquidity", 480), ("Evidence bar", 0)]
    )
    assert "512" in html and "0" in html and "ri-funnel" in html


def test_funnel_source_clean():
    src = inspect.getsource(funnel).lower()
    for w in FORBIDDEN_WORDS:
        assert w not in src
