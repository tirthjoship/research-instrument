"""Shared gating logic for in-app Run buttons (Home brief, Screener).

Single-flight + cooldown + freshness so a public deploy can't be hammered
into repeated live yfinance/Gemini pipeline runs.
"""

from __future__ import annotations

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
