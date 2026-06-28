# tests/test_sa_synthesis.py
import inspect
from types import SimpleNamespace

from adapters.visualization.tabs.stock_analysis import synthesis
from domain.fit import FORBIDDEN_WORDS


def _result(**over):
    base = dict(
        peer_percentiles={"P/E": 78.0},
        info={"revenueGrowth": 0.69},
        analyst_panel=SimpleNamespace(mean_rating=1.6, data_gap=False),
        insider_transactions=[{"value": -48_000_000}],
        buzz_signals=[
            SimpleNamespace(sentiment_raw=0.3),
            SimpleNamespace(sentiment_raw=0.1),
        ],
    )
    base.update(over)
    return SimpleNamespace(**base)


def test_view_builds_five_chips_with_anchors():
    v = synthesis.build_synthesis_view(_result())
    keys = {c.label for c in v.chips}
    assert keys == {"Valuation", "Growth", "Analysts", "Insiders", "Buzz"}
    anchors = {c.anchor for c in v.chips}
    assert "sa-fundamentals" in anchors and "sa-signals" in anchors
    # every chip carries a non-empty measurement basis (measured colour)
    assert all(c.basis for c in v.chips)


def test_valuation_top_quartile_is_amber():
    v = synthesis.build_synthesis_view(_result())
    val = next(c for c in v.chips if c.label == "Valuation")
    assert val.tone == "amber" and "78" in val.value


def test_insiders_grey_not_red_with_falsified_caveat():
    v = synthesis.build_synthesis_view(_result())
    ins = next(c for c in v.chips if c.label == "Insiders")
    # spec D11 + anti-false-claim: a FALSIFIED signal must NOT be coloured as bad
    assert ins.tone == "grey"
    assert "falsified" in ins.basis.lower() or "falsified" in ins.meaning.lower()


def test_html_has_prose_chips_jumpnav_and_tooltips():
    html = synthesis.build_synthesis_html(synthesis.build_synthesis_view(_result()))
    assert "Story this week" in html and "NOT A FORECAST" in html
    assert 'class="sa-prose"' in html
    assert html.count("sa-cchip") >= 5
    assert html.count("sa-tip") >= 5  # working tooltip on every chip
    assert (
        'href="#sa&#45;fundamentals"' in html
    )  # hyphen encoded as &#45; to allow index-ordering tests


def test_datagap_renders_grey_chip():
    r = _result(peer_percentiles={})
    v = synthesis.build_synthesis_view(r)
    val = next(c for c in v.chips if c.label == "Valuation")
    assert val.tone == "grey"


def test_no_streamlit_and_clean():
    src = inspect.getsource(synthesis)
    assert "import streamlit" not in src
    low = src.lower()
    for w in FORBIDDEN_WORDS:
        assert w not in low
