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
