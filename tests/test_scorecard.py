from domain.fit import FitFlag, FitVerdict


def _row(ticker, grade, flags=()):
    from application.batch_fit_use_case import BatchFitRow

    return BatchFitRow(
        ticker=ticker,
        verdict=FitVerdict(
            ticker=ticker,
            evidence_grade=grade,
            fit_flags=tuple(flags),
            summary=f"{ticker} summary.",
        ),
        fetch_ok=True,
    )


def test_scorecard_ranks_strong_first():
    from adapters.visualization.components.scorecard import rank_rows

    rows = [_row("AAA", "WEAK"), _row("BBB", "STRONG"), _row("CCC", "MODERATE")]
    ranked = rank_rows(rows)
    assert [r.ticker for r in ranked] == ["BBB", "CCC", "AAA"]


def test_scorecard_render_no_raise():
    from adapters.visualization.components.scorecard import render_scorecard

    render_scorecard(
        [
            _row(
                "NVDA",
                "STRONG",
                [FitFlag("BETA_AMPLIFY", "deepens market bet", "WARNING")],
            )
        ]
    )


def test_scorecard_source_has_no_forbidden_words():
    import inspect

    from adapters.visualization.components import scorecard
    from domain.fit import FORBIDDEN_WORDS

    src = inspect.getsource(scorecard).lower()
    for word in FORBIDDEN_WORDS:
        assert word not in src, f"forbidden word {word!r} in scorecard source"


def test_snowflake_source_has_no_forbidden_words():
    import inspect

    from adapters.visualization.components import snowflake
    from domain.fit import FORBIDDEN_WORDS

    src = inspect.getsource(snowflake).lower()
    for word in FORBIDDEN_WORDS:
        assert word not in src, f"forbidden word {word!r} in snowflake source"
