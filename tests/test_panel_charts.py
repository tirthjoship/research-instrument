import inspect

from adapters.visualization.components import panel_charts
from domain.fit import FORBIDDEN_WORDS


def test_peer_bars_marks_self():
    html = panel_charts.peer_bars(
        [("NVDA", 52.0, True), ("AMD", 38.0, False)], unit="x"
    )
    assert "NVDA" in html and "52" in html and "AMD" in html
    assert "var(--ri-amber)" in html  # self row tinted


def test_trend_lines_emit_polylines():
    svg = panel_charts.trend_lines([("gross", [70.0, 72.0, 75.0], "#1F9254")])
    assert "<svg" in svg and "polyline" in svg and "gross" in svg


def test_trend_lines_empty_is_blank():
    assert panel_charts.trend_lines([]) == ""


def test_marker_range_positions_and_band():
    html = panel_charts.marker_range(
        28.0, 68.0, [(52.0, "now 52x", "#0F6E80")], band=(35.0, 55.0)
    )
    assert "now 52x" in html and "sa-rangebar" in html


def test_marker_range_datagap_when_no_span():
    html = panel_charts.marker_range(0.0, 0.0, [])
    assert "data gap" in html.lower() or "—" in html


def test_clean():
    src = inspect.getsource(panel_charts).lower()
    for w in FORBIDDEN_WORDS:
        assert w not in src
