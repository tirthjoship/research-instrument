"""TDD tests for adapters/visualization/components/gemini_read.py (S6).

HONESTY INVARIANT: CaseContext built here NEVER contains score/composite/grade fields.
The rendered block is a companion BESIDE the score — never an input to it.
"""

from __future__ import annotations

# ---------------------------------------------------------------------------
# Task 1: CaseContext builder from already-fetched data
# ---------------------------------------------------------------------------


def test_build_context_uses_only_supplied_facts_and_news() -> None:
    from adapters.visualization.components.gemini_read import build_case_context

    ctx = build_case_context(
        ticker="SPG",
        facts={"occupancy": "recovering"},
        news=[{"title": "REIT rates ease"}],
    )
    assert ctx.ticker == "SPG"
    # CaseContext must carry NO score/composite/grade field — honesty invariant
    assert not hasattr(ctx, "composite")
    assert not hasattr(ctx, "evidence_grade")
    assert not hasattr(ctx, "score")


def test_build_context_facts_appear_in_context() -> None:
    from adapters.visualization.components.gemini_read import build_case_context

    ctx = build_case_context(
        ticker="AAPL",
        facts={"revenue": "grew 12%", "margin": "stable"},
        news=[{"title": "Apple beats estimates"}, {"title": "Strong iPhone cycle"}],
    )
    # facts dict values should be represented in the facts tuple
    assert any("grew 12%" in f for f in ctx.facts)
    # news titles should be in the news tuple as (source, title) pairs
    assert any("Apple beats estimates" in title for _, title in ctx.news)


def test_build_context_empty_inputs_no_error() -> None:
    from adapters.visualization.components.gemini_read import build_case_context

    ctx = build_case_context(ticker="XYZ", facts={}, news=[])
    assert ctx.ticker == "XYZ"
    assert ctx.facts == ()
    assert ctx.news == ()


# ---------------------------------------------------------------------------
# Task 2: Render attributed block, fail-safe
# ---------------------------------------------------------------------------


def test_render_gemini_read_attributed_and_safe() -> None:
    from adapters.visualization.components.gemini_read import render_gemini_read
    from domain.case_models import CasePoint, CaseResult

    res = CaseResult(
        in_favor=(CasePoint("occupancy recovering", "reported"),),
        to_watch=(CasePoint("refi wall", "macro"),),
        data_gap=False,
    )
    html = render_gemini_read(res)
    assert "Google-AI read" in html
    assert "never an input" in html.lower()  # attribution disclaimer
    assert "occupancy recovering" in html
    assert "refi wall" in html


def test_render_gemini_read_data_gap_hides_or_notes() -> None:
    from adapters.visualization.components.gemini_read import render_gemini_read
    from domain.case_models import CaseResult

    res = CaseResult((), (), True)
    html = render_gemini_read(res)
    assert "unavailable" in html.lower() or html == ""


def test_gemini_read_no_forbidden_words() -> None:
    from adapters.visualization.components.gemini_read import render_gemini_read
    from domain.case_models import CasePoint, CaseResult

    res = CaseResult(
        in_favor=(CasePoint("strong demand", "analyst"),),
        to_watch=(CasePoint("valuation stretched", "fundamental"),),
        data_gap=False,
    )
    low = render_gemini_read(res).lower()
    # Check as standalone tokens (word boundaries)
    import re

    for w in ("buy", "sell", "winner", "conviction", "predict", "alpha", "outperform"):
        assert w not in re.split(
            r"\W+", low
        ), f"Forbidden word '{w}' found as a token in rendered HTML"


def test_render_gemini_read_in_favor_marker_present() -> None:
    """▲ marker or equivalent must appear in rendered in-favor section."""
    from adapters.visualization.components.gemini_read import render_gemini_read
    from domain.case_models import CasePoint, CaseResult

    res = CaseResult(
        in_favor=(CasePoint("dividend raised", "reported"),),
        to_watch=(),
        data_gap=False,
    )
    html = render_gemini_read(res)
    # Either Unicode ▲ or text "favor" or "in favor" must appear
    assert "▲" in html or "favor" in html.lower() or "in-favor" in html.lower()


def test_render_gemini_read_to_watch_marker_present() -> None:
    """▼ marker or equivalent must appear in rendered to-watch section."""
    from adapters.visualization.components.gemini_read import render_gemini_read
    from domain.case_models import CasePoint, CaseResult

    res = CaseResult(
        in_favor=(),
        to_watch=(CasePoint("rate sensitivity", "macro"),),
        data_gap=False,
    )
    html = render_gemini_read(res)
    assert "▼" in html or "watch" in html.lower()


# ---------------------------------------------------------------------------
# Task 4: Static honesty gate — gemini_read + research_candidates never
#          reference composite/factor score values when building CaseContext.
# ---------------------------------------------------------------------------


def test_gemini_read_module_does_not_import_composite_or_score() -> None:
    """gemini_read.py must not import or reference composite/score/evidence_grade."""
    import ast
    import inspect

    import adapters.visualization.components.gemini_read as mod

    source = inspect.getsource(mod)
    tree = ast.parse(source)

    # Collect all Name and Attribute nodes that might reference score fields
    forbidden_refs = {"composite", "evidence_grade", "factor_score", "score"}
    found: list[str] = []

    for node in ast.walk(tree):
        if isinstance(node, ast.Name) and node.id in forbidden_refs:
            found.append(node.id)
        elif isinstance(node, ast.Attribute) and node.attr in forbidden_refs:
            found.append(node.attr)

    assert not found, (
        f"gemini_read.py references forbidden score fields: {found}. "
        "CaseContext must be built from facts/news only — never from scores."
    )


def test_maybe_render_gemini_does_not_pass_composite_to_build_context() -> None:
    """maybe_render_gemini signature accepts facts+news only — no composite/score param."""
    import inspect

    from adapters.visualization.tabs.research_candidates import maybe_render_gemini

    sig = inspect.signature(maybe_render_gemini)
    param_names = set(sig.parameters.keys())

    # These score-derived fields must NEVER appear as parameters
    forbidden_params = {"composite", "score", "evidence_grade", "factor_scores"}
    collisions = param_names & forbidden_params
    assert not collisions, (
        f"maybe_render_gemini has forbidden score-bearing params: {collisions}. "
        "Gemini context must never receive composite or score values."
    )


def test_build_case_context_result_has_exactly_three_fields() -> None:
    """CaseContext returned by build_case_context must have ticker, facts, news only."""
    import dataclasses

    from adapters.visualization.components.gemini_read import build_case_context

    ctx = build_case_context(
        ticker="TEST",
        facts={"momentum": "above trend"},
        news=[{"title": "Strong earnings", "source": "Reuters"}],
    )
    field_names = {f.name for f in dataclasses.fields(ctx)}
    assert field_names == {"ticker", "facts", "news"}, (
        f"CaseContext has unexpected fields: {field_names}. "
        "Must only contain ticker, facts, news — no score/composite/grade."
    )
