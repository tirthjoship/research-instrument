import inspect
from types import SimpleNamespace

from adapters.visualization.components.radar_svg import RadarAxis
from adapters.visualization.tabs.stock_analysis import fit_card
from domain.fit import FORBIDDEN_WORDS


def _fit():
    return SimpleNamespace(
        evidence_grade="B",
        summary="Strong on momentum and quality; rich on value.",
        fit_flags=(
            SimpleNamespace(
                severity="CAUTION", message="Concentration — adds to semis tilt"
            ),
            SimpleNamespace(severity="CAUTION", message="Beta 1.7 vs 1.1 book beta"),
            SimpleNamespace(severity="INFO", message="Liquidity ample"),
        ),
    )


def _axes():
    return [
        RadarAxis("Value", 22, "#d08218"),
        RadarAxis("Quality", 88, "#0F6E80"),
        RadarAxis("Mom", 95, "#2f9e44"),
    ]


def test_view_maps_grade_summary_flags():
    v = fit_card.build_fit_card_view(_fit())
    assert v.grade == "B" and "momentum" in v.summary.lower()
    assert len(v.flags) == 3
    assert "FALSIFIED" in v.falsified_note


def test_fit_card_html_has_grade_flags_and_falsified():
    v = fit_card.build_fit_card_view(_fit())
    html = fit_card.build_fit_card_html(v)
    assert "GRADE B" in html
    assert "Concentration" in html and "Beta 1.7" in html
    assert "FALSIFIED" in html and "sa-tip" not in html.replace(
        "FALSIFIED", ""
    )  # falsified is plain copy, not a tip-only


def test_section_html_has_radar_legend_and_card():
    v = fit_card.build_fit_card_view(_fit())
    html = fit_card.build_snowflake_fit_html(_axes(), v)
    assert "<svg" in html and 'class="sa-twocol-fit"' in html
    assert "sa-lgnd" in html and "median (50th)" in html
    assert "GRADE B" in html


def test_colour_key_states_bands():
    assert (
        "atypical" in fit_card.COLOUR_KEY_HTML
        and "threshold" in fit_card.COLOUR_KEY_HTML
    )
    assert 'class="sa-ckey"' in fit_card.COLOUR_KEY_HTML


def test_handles_missing_fit():
    v = fit_card.build_fit_card_view(None)
    assert v.grade == "—" and v.flags == ()
    html = fit_card.build_fit_card_html(v)
    assert "sa-grade" in html


def test_no_streamlit_and_clean():
    src = inspect.getsource(fit_card)
    assert "import streamlit" not in src
    low = src.lower()
    for w in FORBIDDEN_WORDS:
        assert w not in low
