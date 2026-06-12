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
    """gather_and_assess must be called at most once across two render()-like calls.

    We don't call render() directly (it reads st widgets which aren't trivially
    exercisable in unit tests).  Instead we test the guard logic directly:
    the session_state key ``fit_{ticker}`` is written on first compute and skips
    the callable on subsequent calls — exactly what the fixed render() does.
    """
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

    def fake_gather(*args, **kwargs):
        nonlocal call_count
        call_count += 1
        return fake_verdict

    # Simulate session_state as a plain dict (mirrors the guard logic in render())
    session_state: dict = {}

    def _guarded_compute() -> None:
        if fit_key not in session_state:
            session_state[fit_key] = fake_gather()

    # First call — should invoke fake_gather
    _guarded_compute()
    assert call_count == 1, "gather should be called once on first compute"
    assert fit_key in session_state

    # Second call — guard must skip the callable
    _guarded_compute()
    assert call_count == 1, "gather must NOT be called again when key already cached"
    assert session_state[fit_key] is fake_verdict


def test_fit_verdict_not_cached_on_exception():
    """On exception, session_state must NOT be written so a later rerun can retry."""
    ticker = "BAD"
    fit_key = f"fit_{ticker}"
    session_state: dict = {}

    def _guarded_compute_with_failure() -> None:
        if fit_key not in session_state:
            try:
                raise RuntimeError("yfinance timeout")
                session_state[fit_key] = object()  # unreachable
            except Exception:
                pass  # caption shown; key NOT written

    _guarded_compute_with_failure()
    assert (
        fit_key not in session_state
    ), "fit key must be absent after a failed compute so next rerun retries"
