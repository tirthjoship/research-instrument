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

        ctx = getattr(st, "context", None)
        if ctx is not None:
            ip = getattr(ctx, "ip_address", None)
            if ip in ("127.0.0.1", "::1"):
                return True
            headers = getattr(ctx, "headers", None)
            if headers is not None:
                host = ""
                if hasattr(headers, "get"):
                    host = str(headers.get("host", "") or headers.get("Host", "") or "")
                if host and any(lb in host.lower() for lb in _LOOPBACK):
                    return True
        return False
    except Exception:  # noqa: BLE001
        return False


def is_local_runtime() -> bool:
    if os.environ.get("STOCKREC_LOCAL_ONLY") != "1":
        return False
    addr = _server_address()
    # Empty address = Streamlit default (localhost). Only reject explicit remote binds.
    if addr and addr not in _LOOPBACK:
        return False
    if not _client_is_loopback():
        return False
    return True


def holdings_upload_enabled() -> bool:
    """Whether the Home tab may show the holdings CSV uploader.

    Always True — unlike is_local_runtime() (which guards the operator's own
    real data / AI-panel quota use), an uploaded CSV is each visitor's own file,
    parsed into a session-scoped temp dir and st.session_state only. It is never
    written to data/personal/ and never persisted or shared across sessions, so
    it is safe to offer on a public hosted deploy too — see
    weekly_brief.py::_stage_csv_upload.
    """
    return True
