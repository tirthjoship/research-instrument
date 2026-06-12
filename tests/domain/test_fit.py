"""Domain tests for the portfolio-fit verdict (pure logic, no IO)."""

from hypothesis import given
from hypothesis import strategies as st

from domain.fit import FORBIDDEN_WORDS, FitVerdict, assess_fit, composite_rank


def _kwargs(**over):
    base = dict(
        ticker="NVDA",
        ticker_composite=1.2,
        universe_composites=[-1.0, 0.0, 0.5, 1.2, 2.0],
        ticker_beta=1.4,
        book_net_spy_beta=1.1,
        book_systematic_share=0.55,
        systematic_share_threshold=0.60,
        position_values={"AAPL": 5000.0, "MSFT": 3000.0, "ARKK": 2000.0},
        trend_state="intact",
        hypothetical_weight=0.02,
    )
    base.update(over)
    return base


def test_composite_rank_basic():
    assert composite_rank(1.2, [-1.0, 0.0, 0.5, 1.2, 2.0]) == 0.75


def test_composite_rank_empty_universe():
    assert composite_rank(1.2, []) is None


def test_grade_strong_at_80th_percentile():
    v = assess_fit(**_kwargs(ticker_composite=2.0))
    assert v.evidence_grade == "STRONG"


def test_grade_unknown_when_no_composite():
    v = assess_fit(**_kwargs(ticker_composite=None))
    assert v.evidence_grade == "UNKNOWN"
    assert any(f.kind == "DATA_GAP" for f in v.fit_flags)


def test_beta_amplify_fires_same_sign_near_threshold():
    v = assess_fit(
        **_kwargs(ticker_beta=1.5, book_net_spy_beta=1.2, book_systematic_share=0.58)
    )
    assert any(
        f.kind == "BETA_AMPLIFY" and f.severity == "WARNING" for f in v.fit_flags
    )


def test_beta_amplify_silent_on_opposite_sign():
    v = assess_fit(**_kwargs(ticker_beta=-0.5))
    assert not any(f.kind == "BETA_AMPLIFY" for f in v.fit_flags)


def test_beta_missing_is_data_gap_not_crash():
    v = assess_fit(**_kwargs(ticker_beta=None))
    assert any(
        f.kind == "DATA_GAP" and "beta" in f.message.lower() for f in v.fit_flags
    )


def test_concentration_reports_rank_of_hypothetical_add():
    v = assess_fit(**_kwargs())
    conc = [f for f in v.fit_flags if f.kind == "CONCENTRATION"]
    assert len(conc) == 1
    assert conc[0].severity == "INFO"


def test_concentration_caution_when_add_would_be_largest():
    v = assess_fit(**_kwargs(hypothetical_weight=0.60))
    conc = [f for f in v.fit_flags if f.kind == "CONCENTRATION"][0]
    assert conc.severity == "CAUTION"


def test_concentration_data_gap_without_positions():
    v = assess_fit(**_kwargs(position_values={}))
    assert not any(f.kind == "CONCENTRATION" for f in v.fit_flags)
    assert any(
        f.kind == "DATA_GAP" and "holding" in f.message.lower() for f in v.fit_flags
    )


def test_trend_state_descriptive_only():
    v = assess_fit(**_kwargs(trend_state="broken"))
    ts = [f for f in v.fit_flags if f.kind == "TREND_STATE"][0]
    assert "broken" in ts.message
    assert "exit" not in ts.message.lower()
    assert "sell" not in ts.message.lower()


@given(
    composite=st.one_of(st.none(), st.floats(-5, 5, allow_nan=False)),
    universe=st.lists(st.floats(-5, 5, allow_nan=False), max_size=50),
    beta=st.one_of(st.none(), st.floats(-3, 3, allow_nan=False)),
    book_beta=st.one_of(st.none(), st.floats(-3, 3, allow_nan=False)),
    share=st.one_of(st.none(), st.floats(0, 1, allow_nan=False)),
    weight=st.floats(0.001, 0.99, allow_nan=False),
)
def test_never_raises_and_never_uses_forbidden_words(
    composite, universe, beta, book_beta, share, weight
):
    v = assess_fit(
        **_kwargs(
            ticker_composite=composite,
            universe_composites=universe,
            ticker_beta=beta,
            book_net_spy_beta=book_beta,
            book_systematic_share=share,
            hypothetical_weight=weight,
        )
    )
    assert isinstance(v, FitVerdict)
    assert v.label == "RESEARCH_ONLY"
    text = (v.summary + " ".join(f.message for f in v.fit_flags)).lower()
    for word in FORBIDDEN_WORDS:
        assert word not in text, f"forbidden word {word!r} in output"


@given(weight=st.floats(0.001, 0.99, allow_nan=False))
def test_hypothetical_add_never_shrinks_book(weight):
    v = assess_fit(**_kwargs(hypothetical_weight=weight))
    assert v.label == "RESEARCH_ONLY"
