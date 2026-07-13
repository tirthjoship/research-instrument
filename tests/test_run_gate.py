"""TDD: adapters.visualization.run_gate.evaluate_run_gate().

Shared gating logic for the in-app "Run brief" / "Run screener" buttons —
single-flight, cooldown, and freshness so a public deploy can't be hammered
into repeated live yfinance/Gemini pipeline runs.
"""

from __future__ import annotations

from adapters.visualization.run_gate import COOLDOWN_SECONDS, evaluate_run_gate


def test_disabled_while_already_running() -> None:
    gate = evaluate_run_gate(staleness_days=5, is_running=True, last_run_ts=None)
    assert gate.can_run is False
    assert gate.reason == "running"


def test_disabled_when_fresh() -> None:
    gate = evaluate_run_gate(staleness_days=0, is_running=False, last_run_ts=None)
    assert gate.can_run is False
    assert gate.reason == "fresh"


def test_disabled_when_no_staleness_info_treated_as_fresh_unknown() -> None:
    """No as_of / brief missing entirely -> nothing to be stale about; a
    caller with no brief at all should offer Run, not block on freshness."""
    gate = evaluate_run_gate(staleness_days=None, is_running=False, last_run_ts=None)
    assert gate.can_run is True
    assert gate.reason == "ready"


def test_disabled_during_cooldown_after_a_recent_run() -> None:
    now = 1_000_000.0
    gate = evaluate_run_gate(
        staleness_days=3,
        is_running=False,
        last_run_ts=now - 60,  # ran 1 minute ago
        now=now,
    )
    assert gate.can_run is False
    assert gate.reason == "cooldown"


def test_enabled_once_cooldown_elapses() -> None:
    now = 1_000_000.0
    gate = evaluate_run_gate(
        staleness_days=3,
        is_running=False,
        last_run_ts=now - COOLDOWN_SECONDS - 1,
        now=now,
    )
    assert gate.can_run is True
    assert gate.reason == "ready"


def test_enabled_when_stale_no_prior_run_no_cooldown() -> None:
    gate = evaluate_run_gate(staleness_days=3, is_running=False, last_run_ts=None)
    assert gate.can_run is True
    assert gate.reason == "ready"
