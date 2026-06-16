from __future__ import annotations

from application.runtime_guard import is_local_runtime


def test_defaults_not_local(monkeypatch):  # type: ignore[no-untyped-def]
    """CI TRIPWIRE: with nothing set, runtime is NOT local → privacy copy must stay hidden."""
    monkeypatch.delenv("STOCKREC_LOCAL_ONLY", raising=False)
    assert is_local_runtime() is False


def test_flag_alone_not_enough(monkeypatch):  # type: ignore[no-untyped-def]
    monkeypatch.setenv("STOCKREC_LOCAL_ONLY", "1")
    monkeypatch.setattr("application.runtime_guard._server_address", lambda: "0.0.0.0")
    assert is_local_runtime() is False  # bound to 0.0.0.0 → treat as remote


def test_all_conditions_true_is_local(monkeypatch):  # type: ignore[no-untyped-def]
    monkeypatch.setenv("STOCKREC_LOCAL_ONLY", "1")
    monkeypatch.setattr(
        "application.runtime_guard._server_address", lambda: "localhost"
    )
    monkeypatch.setattr("application.runtime_guard._client_is_loopback", lambda: True)
    assert is_local_runtime() is True


def test_risk_tab_omits_ai_panel_when_not_local(monkeypatch):  # type: ignore[no-untyped-def]
    """INTEGRATION TRIPWIRE: risk tab must never embed AI HTML when not running locally.

    render_risk_second_opinion returns "" off-local (privacy fail-safe).  An empty
    string contains no AI-panel markers — specifically the distinctive CSS class
    'risk-ai' that wraps every non-empty AI panel output.
    """
    import adapters.visualization.components.risk_second_opinion as ai_mod
    from domain.case_models import CasePoint, CaseResult

    monkeypatch.setattr(ai_mod, "is_local_runtime", lambda: False)

    populated_result = CaseResult(
        in_favor=(CasePoint(text="Strong cash flow", source_tag="reported"),),
        to_watch=(CasePoint(text="Rising rates", source_tag="macro"),),
        data_gap=False,
    )

    result = ai_mod.render_risk_second_opinion(result=populated_result)

    # Primary guarantee: nothing rendered off-local even with a real result.
    assert result == "", (
        "render_risk_second_opinion must return '' when is_local_runtime() is False; "
        f"got: {result!r}"
    )

    # Derived guarantee: the empty string contains no AI-panel markers.
    assert (
        "risk-ai" not in result
    ), "AI-panel CSS class 'risk-ai' must not appear in off-local output"
