"""TDD tests for adapters.visualization.components.risk_second_opinion — fail first, then implement."""

from __future__ import annotations

import pytest

from domain.case_models import CasePoint, CaseResult
from domain.fit import FORBIDDEN_WORDS


def _minimal_result() -> CaseResult:
    return CaseResult(
        in_favor=(
            CasePoint(text="Macro beta within historical range", source_tag="macro"),
        ),
        to_watch=(
            CasePoint(text="Concentration elevated above threshold", source_tag="risk"),
        ),
        data_gap=False,
    )


def test_render_hidden_when_not_local(monkeypatch: pytest.MonkeyPatch) -> None:
    """render_risk_second_opinion returns '' when is_local_runtime() is False."""
    from adapters.visualization.components.risk_second_opinion import (
        render_risk_second_opinion,
    )

    monkeypatch.setattr(
        "adapters.visualization.components.risk_second_opinion.is_local_runtime",
        lambda: False,
    )
    assert render_risk_second_opinion(result=None) == ""


def test_render_hidden_when_not_local_with_result(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Even with a valid result, returns '' when not local."""
    import adapters.visualization.components.risk_second_opinion as mod
    from adapters.visualization.components.risk_second_opinion import (
        render_risk_second_opinion,
    )

    monkeypatch.setattr(mod, "is_local_runtime", lambda: False)
    assert render_risk_second_opinion(result=_minimal_result()) == ""


def test_render_present_when_local(monkeypatch: pytest.MonkeyPatch) -> None:
    """Returns non-empty HTML when local and result is valid; contains Google AI + RESEARCH badge."""
    import adapters.visualization.components.risk_second_opinion as mod
    from adapters.visualization.components.risk_second_opinion import (
        render_risk_second_opinion,
    )

    monkeypatch.setattr(mod, "is_local_runtime", lambda: True)
    html = render_risk_second_opinion(result=_minimal_result())
    assert "Google AI" in html
    assert "RESEARCH" in html.upper()
    assert not any(w in html.lower() for w in FORBIDDEN_WORDS)


def test_render_no_forbidden_words_in_data_gap_path(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """data_gap=True path also emits no forbidden words."""
    import adapters.visualization.components.risk_second_opinion as mod
    from adapters.visualization.components.risk_second_opinion import (
        render_risk_second_opinion,
    )

    monkeypatch.setattr(mod, "is_local_runtime", lambda: True)
    gap_result = CaseResult(in_favor=(), to_watch=(), data_gap=True)
    html = render_risk_second_opinion(result=gap_result)
    assert not any(w in html.lower() for w in FORBIDDEN_WORDS)


def test_render_attributed_badge_present(monkeypatch: pytest.MonkeyPatch) -> None:
    """ATTRIBUTED badge text must be present in the rendered HTML."""
    import adapters.visualization.components.risk_second_opinion as mod
    from adapters.visualization.components.risk_second_opinion import (
        render_risk_second_opinion,
    )

    monkeypatch.setattr(mod, "is_local_runtime", lambda: True)
    html = render_risk_second_opinion(result=_minimal_result())
    assert "ATTRIBUTED" in html


def test_render_points_included(monkeypatch: pytest.MonkeyPatch) -> None:
    """CasePoint text from in_favor and to_watch must appear in the HTML."""
    import adapters.visualization.components.risk_second_opinion as mod
    from adapters.visualization.components.risk_second_opinion import (
        render_risk_second_opinion,
    )

    monkeypatch.setattr(mod, "is_local_runtime", lambda: True)
    result = _minimal_result()
    html = render_risk_second_opinion(result=result)
    for pt in result.in_favor:
        assert pt.text in html
    for pt in result.to_watch:
        assert pt.text in html


def test_render_none_result_when_local_returns_stub(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """result=None with local runtime returns a small data-gap stub (not empty string).

    R07 spec: when LOCAL but cache empty, show 'ri-sec' header + one-line card
    prompting user to run weekly-brief with GEMINI_API_KEY.
    """
    import adapters.visualization.components.risk_second_opinion as mod
    from adapters.visualization.components.risk_second_opinion import (
        render_risk_second_opinion,
    )

    monkeypatch.setattr(mod, "is_local_runtime", lambda: True)
    html = render_risk_second_opinion(result=None)
    # Must be a non-empty stub, not blank
    assert html != "", "Local + cache empty must return a stub, not empty string"
    # Must contain the ri-sec section heading
    assert "ri-sec" in html, "Data-gap stub must include the ri-sec section heading"
    # Must contain prompt to run weekly-brief
    assert (
        "weekly-brief" in html.lower()
        or "weekly_brief" in html.lower()
        or "GEMINI_API_KEY" in html
    )
    # Must NOT contain forbidden words
    assert not any(w in html.lower() for w in FORBIDDEN_WORDS)


def test_render_none_result_when_off_local_returns_empty(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """result=None with off-local runtime MUST return '' (privacy fail-safe)."""
    import adapters.visualization.components.risk_second_opinion as mod
    from adapters.visualization.components.risk_second_opinion import (
        render_risk_second_opinion,
    )

    monkeypatch.setattr(mod, "is_local_runtime", lambda: False)
    assert (
        render_risk_second_opinion(result=None) == ""
    ), "Off-local + None result must return '' — never reveal data-gap info off-local"


def test_render_section_heading_present(monkeypatch: pytest.MonkeyPatch) -> None:
    """When local + result valid, ri-sec section heading must appear above the card."""
    import adapters.visualization.components.risk_second_opinion as mod
    from adapters.visualization.components.risk_second_opinion import (
        render_risk_second_opinion,
    )

    monkeypatch.setattr(mod, "is_local_runtime", lambda: True)
    html = render_risk_second_opinion(result=_minimal_result())
    assert (
        "ri-sec" in html
    ), "ri-sec section heading must be present when result is valid"
    # Heading must appear BEFORE the card div
    assert html.index("ri-sec") < html.index(
        "risk-ai"
    ), "ri-sec heading must appear before the .risk-ai card div"
    # Heading text must include 'Second opinion' and 'Google AI'
    assert "Second opinion" in html
    assert "Google AI" in html


def test_render_rerun_button_stub_present(monkeypatch: pytest.MonkeyPatch) -> None:
    """When local + result valid, a non-interactive re-run instruction must appear.

    The control is a styled span (not a disabled button) so it reads as a CLI
    instruction rather than a broken widget.  No live API call is wired at render time.
    """
    import adapters.visualization.components.risk_second_opinion as mod
    from adapters.visualization.components.risk_second_opinion import (
        render_risk_second_opinion,
    )

    monkeypatch.setattr(mod, "is_local_runtime", lambda: True)
    html = render_risk_second_opinion(result=_minimal_result())
    # Non-interactive label must carry the .risk-aibtn class
    assert "risk-aibtn" in html, "Re-run label must use .risk-aibtn class"
    # Must NOT be a disabled button — the old broken pattern is gone
    assert "<button" not in html, "Re-run control must not be a <button> element"
    # Must mention weekly-brief so the user knows how to trigger a real re-run
    assert (
        "weekly-brief" in html
    ), "Re-run label must reference the weekly-brief CLI command"
