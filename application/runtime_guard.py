"""Fail-safe local-only guard. Default = NOT local, so a hosted deploy can never expose
the 'stays on your machine' privacy promise by accident."""

from __future__ import annotations

import os

_LOOPBACK = {"localhost", "127.0.0.1", "::1"}


def _server_address() -> str:
    try:
        import streamlit as st  # verify API via context7 (st.get_option)

        return str(st.get_option("server.address") or "")
    except Exception:  # noqa: BLE001
        return ""


def _client_is_loopback() -> bool:
    try:
        import streamlit as st

        host = getattr(getattr(st, "context", None), "headers", {}) or {}
        # best-effort: if Streamlit doesn't expose the client host, treat as NOT loopback (fail-safe)
        forwarded = host.get("Host", "") if hasattr(host, "get") else ""
        return any(lb in forwarded for lb in _LOOPBACK)
    except Exception:  # noqa: BLE001
        return False


def is_local_runtime() -> bool:
    if os.environ.get("STOCKREC_LOCAL_ONLY") != "1":
        return False
    if _server_address() not in _LOOPBACK:
        return False
    if not _client_is_loopback():
        return False
    return True
