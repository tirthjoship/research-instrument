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
    assert "<svg" in svg and "polyline" in svg
    # end-of-line text must not be clipped by the axis-wrapper flex box
    assert "overflow:visible" in svg


def test_trend_lines_single_series_omits_inline_label():
    # one line -> the subhead names it; an inline SVG label is redundant clutter
    svg = panel_charts.trend_lines([("gross", [70.0, 72.0, 75.0], "#1F9254")])
    assert "<text" not in svg


def test_trend_lines_multi_series_labels_each_line():
    svg = panel_charts.trend_lines(
        [
            ("Cash", [40.0, 45.0, 53.0], "#1F9254"),
            ("Debt", [10.0, 11.0, 9.0], "#9aa6aa"),
        ]
    )
    assert "Cash" in svg and "Debt" in svg and svg.count("<text") == 2


def test_trend_lines_empty_is_blank():
    assert panel_charts.trend_lines([]) == ""


def test_trend_lines_render_y_axis_minmax_with_unit():
    html = panel_charts.trend_lines(
        [("gross", [70.0, 72.0, 75.0], "#1F9254")], unit="%"
    )
    # max and min of the combined series shown as HTML axis numbers
    assert "75%" in html and "70%" in html
    # axis numbers use the small mono axis-label treatment, not SVG <text>
    assert "font-size:7.5px" in html


def test_trend_lines_render_x_labels_when_given():
    html = panel_charts.trend_lines(
        [("RS", [100.0, 104.0, 96.0], "#0F6E80")], x_labels=("3m ago", "now")
    )
    assert "3m ago" in html and "now" in html


def test_stacked_bar_one_bar_with_segments_and_legend():
    html = panel_charts.stacked_bar(
        [
            ("Institutions", 66.0, "#0F6E80"),
            ("Insiders", 4.0, "#b45309"),
            ("Public", 30.0, "#cdd7d9"),
        ]
    )
    # single bar, every segment labelled with its share in the legend
    assert "Institutions" in html and "66%" in html
    assert "Insiders" in html and "Public" in html
    assert html.count("<svg") == 0  # pure HTML, not an SVG


def test_horizon_compare_bars_show_stock_and_benchmark():
    html = panel_charts.horizon_compare_bars(
        [("1Y", 25.0, 14.0, True), ("3Y", 97.0, 40.0, False)]
    )
    assert "1Y" in html and "3Y" in html
    assert "+25%" in html and "+14%" in html  # stock and S&P values both shown
    assert "S&P" in html
    assert "var(--ri-amber)" in html  # focus horizon highlighted


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
