"""Whole-app password gate wiring in dashboard.py — item 4 of the Cloud deploy
scaling design. Bounds quota/rate-limit exposure to invited friends rather
than arbitrary internet visitors."""

from __future__ import annotations

import adapters.visualization.dashboard as dash_mod


def test_access_gate_skipped_when_not_required(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    monkeypatch.setattr(dash_mod, "is_access_gate_required", lambda: False)
    assert dash_mod._render_access_gate() is True


def test_access_gate_passes_when_already_granted(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    monkeypatch.setattr(dash_mod, "is_access_gate_required", lambda: True)
    monkeypatch.setattr(
        dash_mod.st, "session_state", {"_access_granted": True}, raising=False
    )
    assert dash_mod._render_access_gate() is True


def test_access_gate_blocks_before_any_button_click(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    monkeypatch.setattr(dash_mod, "is_access_gate_required", lambda: True)
    monkeypatch.setattr(dash_mod.st, "session_state", {}, raising=False)
    monkeypatch.setattr(dash_mod.st, "text_input", lambda *a, **k: "")  # noqa: ARG005
    monkeypatch.setattr(dash_mod.st, "button", lambda *a, **k: False)  # noqa: ARG005
    assert dash_mod._render_access_gate() is False


def test_access_gate_grants_on_correct_password(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    monkeypatch.setenv("APP_PASSWORD", "hunter2")
    monkeypatch.setattr(dash_mod, "is_access_gate_required", lambda: True)
    session: dict[str, object] = {}
    monkeypatch.setattr(dash_mod.st, "session_state", session, raising=False)
    monkeypatch.setattr(
        dash_mod.st, "text_input", lambda *a, **k: "hunter2"
    )  # noqa: ARG005
    monkeypatch.setattr(dash_mod.st, "button", lambda *a, **k: True)  # noqa: ARG005
    rerun_calls: list[int] = []
    monkeypatch.setattr(dash_mod.st, "rerun", lambda: rerun_calls.append(1))

    result = dash_mod._render_access_gate()

    assert session.get("_access_granted") is True
    assert rerun_calls == [1]
    # rerun() halts the current script run for real; the return value is moot
    # in production but must not be True here (session flips on the *next* run).
    assert result is False


def test_access_gate_wrong_password_shows_error_and_stays_blocked(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    monkeypatch.setenv("APP_PASSWORD", "hunter2")
    monkeypatch.setattr(dash_mod, "is_access_gate_required", lambda: True)
    monkeypatch.setattr(dash_mod.st, "session_state", {}, raising=False)
    monkeypatch.setattr(
        dash_mod.st, "text_input", lambda *a, **k: "wrong"
    )  # noqa: ARG005
    monkeypatch.setattr(dash_mod.st, "button", lambda *a, **k: True)  # noqa: ARG005
    errors: list[str] = []
    monkeypatch.setattr(dash_mod.st, "error", lambda msg: errors.append(msg))

    assert dash_mod._render_access_gate() is False
    assert errors


def test_access_gate_unset_app_password_fails_closed_even_on_click(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    """If APP_PASSWORD is unset, no entered value can ever pass — the safe
    default falls out of check_password's own comparison, not a branch here."""
    monkeypatch.delenv("APP_PASSWORD", raising=False)
    monkeypatch.setattr(dash_mod, "is_access_gate_required", lambda: True)
    session: dict[str, object] = {}
    monkeypatch.setattr(dash_mod.st, "session_state", session, raising=False)
    monkeypatch.setattr(
        dash_mod.st, "text_input", lambda *a, **k: "anything"
    )  # noqa: ARG005
    monkeypatch.setattr(dash_mod.st, "button", lambda *a, **k: True)  # noqa: ARG005
    monkeypatch.setattr(dash_mod.st, "error", lambda msg: None)  # noqa: ARG005

    assert dash_mod._render_access_gate() is False
    assert "_access_granted" not in session
