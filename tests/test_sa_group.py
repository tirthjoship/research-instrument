import inspect

from adapters.visualization.tabs.stock_analysis import group
from adapters.visualization.tabs.stock_analysis.group import MicroTile
from domain.fit import FORBIDDEN_WORDS


def _tiles():
    return [
        MicroTile("Valuation", "78th · rich", "#d08218"),
        MicroTile("Growth", "+69%", "#2f9e44"),
        MicroTile("Health", "solid", "#0F6E80"),
    ]


def test_shell_is_collapsed_details_with_anchor():
    html = group.build_group_shell(
        anchor="sa-fundamentals",
        name="Fundamentals",
        grade="B",
        week_delta="▲ P/E +6pts",
        micro_tiles=_tiles(),
    )
    assert '<details class="sa-group"' in html and 'id="sa-fundamentals"' in html
    assert (
        "open" not in html.split(">")[0]
    )  # collapsed by default (no open attr on the details tag)
    assert "<summary" in html


def test_header_has_name_grade_week_and_chevron():
    html = group.build_group_shell(
        anchor="x",
        name="Fundamentals",
        grade="B",
        week_delta="▲ target +$8",
        micro_tiles=_tiles(),
    )
    assert "Fundamentals" in html and "GRADE B" in html
    assert "target +$8" in html and "sa-chev" in html


def test_micro_tiles_render_with_category_dot():
    html = group.build_group_shell(
        anchor="x", name="F", grade="B", week_delta="", micro_tiles=_tiles()
    )
    assert html.count("sa-gt") == 3
    assert "#d08218" in html and "78th · rich" in html


def test_inner_html_passthrough():
    html = group.build_group_shell(
        anchor="x",
        name="F",
        grade="B",
        week_delta="",
        micro_tiles=_tiles(),
        inner_html='<div class="probe"></div>',
    )
    assert '<div class="probe">' in html


def test_escapes_text():
    html = group.build_group_shell(
        anchor="x",
        name="<n>",
        grade="B",
        week_delta="",
        micro_tiles=[MicroTile("<l>", "<v>", "#d08218")],
    )
    assert "<n>" not in html.replace("<details", "").replace("<summary", "")
    assert "&lt;n&gt;" in html


def test_no_streamlit_and_clean():
    src = inspect.getsource(group)
    assert "import streamlit" not in src
    low = src.lower()
    for w in FORBIDDEN_WORDS:
        assert w not in low
