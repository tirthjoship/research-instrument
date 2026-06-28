import inspect

from adapters.visualization.tabs.stock_analysis import panel
from adapters.visualization.tabs.stock_analysis.panel import Verdict
from domain.fit import FORBIDDEN_WORDS


def test_build_panel_has_all_anatomy():
    html = panel.build_panel(
        number=1,
        name="Valuation",
        dot_colour="#d08218",
        info_html="<span>i</span>",
        chips_html='<span class="sa-chip t-amber">RICH</span>',
        claim="Rich on price",
        reframe="Top-quartile multiples, yet PEG <1.",
        strip_html='<div class="sa-strip"></div>',
        viz_left="<svg></svg>",
        viz_right="<svg></svg>",
        verdicts=[
            Verdict("cau", "Little margin for a miss."),
            Verdict("pos", "PEG <1."),
        ],
        drill="open full valuation",
    )
    assert 'class="sa-pnl"' in html
    assert "Valuation" in html and "#d08218" in html
    assert "RICH" in html and "Rich on price" in html
    assert "sa-strip" in html and html.count("<svg") == 2
    assert html.count("sa-vb") == 2 and "Little margin" in html
    # drill links removed — the "open full …" deeper view was never built (DATA-GAP)
    assert "sa-drill" not in html and "open full" not in html


def test_escapes_name_and_claim():
    html = panel.build_panel(
        number=1,
        name="<n>",
        dot_colour="#000",
        info_html="",
        chips_html="",
        claim="<c>",
        reframe="<r>",
        strip_html="",
        viz_left="",
        viz_right="",
        verdicts=[],
        drill="<d>",
    )
    assert "<n>" not in html.replace("<svg", "") and "&lt;n&gt;" in html


def test_no_streamlit_and_clean():
    src = inspect.getsource(panel)
    assert "import streamlit" not in src
    low = src.lower()
    for w in FORBIDDEN_WORDS:
        assert w not in low
