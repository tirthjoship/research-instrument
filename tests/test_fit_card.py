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


def test_fit_verdict_cached_after_first_compute():
    """_ensure_fit_cached fires compute_fn exactly once across two calls for the same key."""
    from adapters.visualization.tabs.stock_analysis import _ensure_fit_cached
    from domain.fit import FitFlag, FitVerdict

    ticker = "AAPL"
    fit_key = f"fit_{ticker}"
    fake_verdict = FitVerdict(
        ticker=ticker,
        evidence_grade="MODERATE",
        fit_flags=(FitFlag("BETA_AMPLIFY", "deepens the market bet", "INFO"),),
        summary="Test summary.",
    )

    call_count = 0

    def compute():
        nonlocal call_count
        call_count += 1
        return fake_verdict

    session_state: dict = {}

    # First call — should invoke compute
    result1 = _ensure_fit_cached(session_state, fit_key, compute)
    assert call_count == 1, "compute should be called once on first call"
    assert result1 is fake_verdict
    assert fit_key in session_state

    # Second call — must return cached value without calling compute again
    result2 = _ensure_fit_cached(session_state, fit_key, compute)
    assert call_count == 1, "compute must NOT be called again when key already cached"
    assert result2 is fake_verdict


def test_fit_verdict_not_cached_on_exception():
    """On exception, _ensure_fit_cached returns None and leaves key absent (retry-able)."""
    from adapters.visualization.tabs.stock_analysis import _ensure_fit_cached

    ticker = "BAD"
    fit_key = f"fit_{ticker}"
    session_state: dict = {}

    def boom():
        raise RuntimeError("yfinance timeout")

    result = _ensure_fit_cached(session_state, fit_key, boom)
    assert result is None, "must return None when compute_fn raises"
    assert (
        fit_key not in session_state
    ), "fit key must be absent after a failed compute so next rerun retries"


def test_grade_badge_html_fit_grades_have_css_class():
    """grade_badge_html for fit evidence grades must return HTML with a non-empty CSS class."""
    from adapters.visualization.components.formatters import grade_badge_html

    for grade in ("STRONG", "MODERATE", "WEAK", "UNKNOWN"):
        html = grade_badge_html(grade)
        # Must contain a non-empty class beyond just "grade-badge"
        # grade_badge_html returns: <span class="grade-badge {css_class}">...</span>
        # So if css_class is empty the class attr would be 'grade-badge ' (trailing space + empty)
        assert (
            'class="grade-badge "' not in html
        ), f"grade_badge_html({grade!r}) has empty CSS class: {html!r}"
        # Positively assert the expected class exists
        assert (
            "grade-" in html
        ), f"grade_badge_html({grade!r}) contains no grade CSS class: {html!r}"
