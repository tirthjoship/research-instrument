"""Shared gating logic for in-app Run buttons (Home brief, Screener).

Single-flight + cooldown + freshness so a public deploy can't be hammered
into repeated live yfinance/Gemini pipeline runs.
"""

from __future__ import annotations

import threading
import time
from dataclasses import dataclass

COOLDOWN_SECONDS = 600  # 10 minutes

RUN_GATE_HELP = {
    "running": "Already running — hang tight.",
    "fresh": "Fresh — less than a day old.",
    "cooldown": "Just ran — please wait before running again.",
    "ready": "Run now.",
}


@dataclass(frozen=True)
class RunGateState:
    can_run: bool
    reason: str  # "running" | "fresh" | "cooldown" | "ready"


def evaluate_run_gate(
    *,
    staleness_days: int | None,
    is_running: bool,
    last_run_ts: float | None,
    now: float | None = None,
) -> RunGateState:
    """Decide whether a Run button should be enabled right now.

    Priority: already running -> fresh (<1 day old) -> cooldown since the
    last completed run -> ready. Unknown staleness (no artifact yet) is
    treated as ready — there is nothing to be "fresh" about.
    """
    if is_running:
        return RunGateState(can_run=False, reason="running")
    if staleness_days is not None and staleness_days < 1:
        return RunGateState(can_run=False, reason="fresh")
    if last_run_ts is not None:
        effective_now = now if now is not None else time.time()
        if (effective_now - last_run_ts) < COOLDOWN_SECONDS:
            return RunGateState(can_run=False, reason="cooldown")
    return RunGateState(can_run=True, reason="ready")


# ---------------------------------------------------------------------------
# Process-global gate state — single-flight + cooldown shared across ALL
# visitors, not per-browser-session.
#
# st.session_state is isolated per visitor, so a gate keyed on it cannot stop
# N different visitors from each independently triggering their own
# full-universe scan (the incident this fixes: Streamlit Cloud shares one
# Python process across every visitor's session, so a plain module-level
# dict — guarded by a lock since multiple visitor threads read/write it
# concurrently — is genuinely process-wide, unlike st.session_state).
# ---------------------------------------------------------------------------

_lock = threading.Lock()
_processing: dict[str, bool] = {}
_last_run_ts: dict[str, float] = {}


def is_processing(name: str) -> bool:
    with _lock:
        return _processing.get(name, False)


def set_processing(name: str, value: bool) -> None:
    with _lock:
        _processing[name] = value


def get_last_run_ts(name: str) -> float | None:
    with _lock:
        return _last_run_ts.get(name)


def set_last_run_ts(name: str, ts: float) -> None:
    with _lock:
        _last_run_ts[name] = ts
