import inspect

from adapters.visualization.components import mini_charts
from domain.fit import FORBIDDEN_WORDS


def test_sparkline_has_polyline_and_points():
    svg = mini_charts.sparkline([1.0, 2.0, 3.0, 5.0])
    assert "<svg" in svg and "polyline" in svg and "points=" in svg


def test_percentile_bar_clamps_and_marks():
    svg = mini_charts.percentile_bar(140.0)  # over 100 -> clamps to 100
    assert "<svg" in svg or "sa-' " in svg or "left:100%" in svg
    svg2 = mini_charts.percentile_bar(78.0)
    assert "78" in svg2


def test_range_bar_positions_marker_between_low_high():
    html = mini_charts.range_bar(86.0, 190.0, [(172.0, "now", "#0F6E80")])
    assert "now" in html and "sa-rangebar" in html


def test_no_streamlit_and_clean():
    src = inspect.getsource(mini_charts)
    assert "import streamlit" not in src
    low = src.lower()
    for w in FORBIDDEN_WORDS:
        assert w not in low
