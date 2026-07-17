import inspect
from types import SimpleNamespace

from adapters.visualization.tabs.stock_analysis import hero
from domain.fit import FORBIDDEN_WORDS


def _result():
    return SimpleNamespace(
        company_name="NVIDIA Corp",
        ticker="NVDA",
        sector="Semiconductors",
        current_price=172.40,
        change_pct=1.28,
        market_cap=4.21e12,
        info={
            "exchange": "NASDAQ",
            "fiftyTwoWeekLow": 86.60,
            "fiftyTwoWeekHigh": 189.50,
        },
    )


def test_view_computes_range_and_formats():
    v = hero.build_hero_view(_result(), grade="B", as_of="Jun 27 2026")
    assert v.exchange == "NASDAQ" and v.sector == "Semiconductors"
    assert v.price == "$172.40"
    assert v.change_down is False and "1.28%" in v.change_label
    assert v.market_cap == "$4.21T"
    assert v.low == "$86.60" and v.high == "$189.50"
    # (172.40-86.60)/(189.50-86.60)*100 = 83.4 -> 83
    assert v.range_pct == 83
    assert "high" in v.range_label.lower()
    assert v.grade_label.startswith("EVIDENCE GRADE B")


def test_negative_change_marks_down():
    r = _result()
    r.change_pct = -2.1
    v = hero.build_hero_view(r)
    assert v.change_down is True and "2.1" in v.change_label


def test_missing_range_data_degrades_gracefully():
    r = _result()
    r.info = {}
    v = hero.build_hero_view(r)
    assert v.range_pct == 0 and v.low == "—" and v.high == "—"
    assert v.exchange == "—"


def test_missing_market_cap_shows_dash_not_zero():
    """yfinance can return marketCap=None for thinly-covered tickers (e.g. small
    NSE-listed companies) -- a real company can never have $0 market cap, so
    this must degrade to the same honest '—' placeholder as missing range
    data, not a fabricated-looking '$0'."""
    r = _result()
    r.market_cap = 0.0
    v = hero.build_hero_view(r)
    assert v.market_cap == "—"


def test_html_contains_identity_price_range_and_grade():
    html = hero.build_hero_html(
        hero.build_hero_view(_result(), grade="B", as_of="Jun 27 2026")
    )
    assert 'class="sa-hero"' in html and "RESEARCH_ONLY" in html
    assert "NVIDIA Corp" in html and "NVDA" in html and "NASDAQ" in html
    assert "$172.40" in html and "$4.21T" in html
    assert 'class="sa-rngw"' in html and "left:83%" in html
    assert "EVIDENCE GRADE B" in html


def test_html_escapes_company_name():
    r = _result()
    r.company_name = "A<b>X"
    html = hero.build_hero_html(hero.build_hero_view(r))
    assert "<b>X" not in html and "&lt;b&gt;X" in html


def test_canadian_ticker_shows_cad_symbol():
    """A TSX-suffixed ticker's price/range/market-cap must show C$, not bare
    $ — showing bare $ would misrepresent CAD amounts as USD."""
    r = _result()
    r.ticker = "RY.TO"
    v = hero.build_hero_view(r, grade="B", as_of="Jun 27 2026")
    assert v.price.startswith("C$")
    assert v.low.startswith("C$") and v.high.startswith("C$")
    assert v.market_cap.startswith("C$")
    assert "$" not in v.price.replace("C$", "")
    assert "$" not in v.market_cap.replace("C$", "")


def test_no_streamlit_and_clean():
    src = inspect.getsource(hero)
    assert "import streamlit" not in src
    low = src.lower()
    for w in FORBIDDEN_WORDS:
        assert w not in low
