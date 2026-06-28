# tests/test_radar_svg.py
import inspect

import pytest

from adapters.visualization.components import radar_svg
from adapters.visualization.components.radar_svg import RadarAxis
from domain.fit import FORBIDDEN_WORDS


def _axes():
    return [
        RadarAxis("Value", 22, "#d08218"),
        RadarAxis("Quality", 88, "#0F6E80"),
        RadarAxis("Mom", 95, "#2f9e44"),
        RadarAxis("Rev", 80, "#5c6bc0"),
        RadarAxis("Trend", 90, "#2aa198"),
        RadarAxis("Fit", 45, "#6b7d84"),
    ]


def test_returns_svg_with_value_polygon_and_dots():
    svg = radar_svg.build_radar_svg(_axes())
    assert svg.startswith("<svg") and svg.rstrip().endswith("</svg>")
    assert svg.count("<polygon") >= 6  # 4 rings + median + value
    assert svg.count("<circle") == 6  # one category dot per axis
    assert "#0F6E80" in svg  # petrol value polygon


def test_labels_show_value_and_category_colour():
    svg = radar_svg.build_radar_svg(_axes())
    assert "Value 22" in svg and "Quality 88" in svg
    assert 'fill="#d08218"' in svg


def test_median_baseline_is_dashed():
    svg = radar_svg.build_radar_svg(_axes(), median=50.0)
    assert "stroke-dasharray" in svg


def test_requires_three_axes():
    with pytest.raises(ValueError):
        radar_svg.build_radar_svg(_axes()[:2])


def test_escapes_labels():
    svg = radar_svg.build_radar_svg(
        [
            RadarAxis("<x>", 10, "#d08218"),
            RadarAxis("B", 20, "#0F6E80"),
            RadarAxis("C", 30, "#2f9e44"),
        ]
    )
    assert (
        "<x>" not in svg.replace("<svg", "").replace("</svg>", "") or "&lt;x&gt;" in svg
    )


def test_clean_of_slop():
    src = inspect.getsource(radar_svg).lower()
    for w in FORBIDDEN_WORDS:
        assert w not in src
