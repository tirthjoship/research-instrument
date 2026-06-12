"""Fit card: render-no-raise + vocabulary guard on rendered output."""


def _verdict():
    from domain.fit import FitFlag, FitVerdict

    return FitVerdict(
        ticker="NVDA",
        evidence_grade="STRONG",
        fit_flags=(
            FitFlag("BETA_AMPLIFY", "deepens the market bet", "WARNING"),
            FitFlag("CONCENTRATION", "would be your #4 position", "INFO"),
        ),
        summary="NVDA sits in the top fifth of the screened universe.",
    )


def test_render_fit_card_no_raise():
    from adapters.visualization.tabs.stock_analysis import _render_fit_card

    _render_fit_card(_verdict(), screen_as_of="2026-06-13")


def test_fit_card_source_has_no_forbidden_words():
    import inspect

    from adapters.visualization.tabs import stock_analysis
    from domain.fit import FORBIDDEN_WORDS

    src = inspect.getsource(stock_analysis._render_fit_card).lower()
    for word in FORBIDDEN_WORDS:
        assert word not in src, f"forbidden word {word!r} in fit card source"


def test_severity_tone_mapping_complete():
    from adapters.visualization.tabs.stock_analysis import _SEVERITY_CLASS

    assert _SEVERITY_CLASS == {
        "INFO": "verdict-neutral",
        "CAUTION": "verdict-caution",
        "WARNING": "verdict-negative",
    }
