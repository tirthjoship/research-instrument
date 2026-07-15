from __future__ import annotations

from application.access_gate import check_password, is_access_gate_required


def test_check_password_correct_matches() -> None:
    assert check_password("hunter2", "hunter2") is True


def test_check_password_wrong_does_not_match() -> None:
    assert check_password("wrong", "hunter2") is False


def test_check_password_empty_secret_always_fails_closed() -> None:
    """Fails closed by construction: an unset APP_PASSWORD (empty/None) must
    never grant access, no matter what is entered — no special-case branch,
    the comparison itself makes the safe default fall out."""
    assert check_password("hunter2", None) is False
    assert check_password("hunter2", "") is False
    assert check_password("", None) is False
    assert check_password("", "") is False


def test_access_gate_required_when_not_local(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    monkeypatch.setattr("application.access_gate.is_local_runtime", lambda: False)
    assert is_access_gate_required() is True


def test_access_gate_not_required_when_local(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    monkeypatch.setattr("application.access_gate.is_local_runtime", lambda: True)
    assert is_access_gate_required() is False
