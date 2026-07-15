"""TDD: adapters.visualization.run_gate.evaluate_run_gate().

Shared gating logic for the in-app "Run brief" / "Run screener" buttons —
single-flight, cooldown, and freshness so a public deploy can't be hammered
into repeated live yfinance/Gemini pipeline runs.
"""

from __future__ import annotations

from adapters.visualization.run_gate import (
    COOLDOWN_SECONDS,
    evaluate_run_gate,
    get_last_run_ts,
    is_processing,
    set_last_run_ts,
    set_processing,
)


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


# ---------------------------------------------------------------------------
# Process-global gate state (single-flight + cooldown shared across ALL
# visitors, not per-browser-session). st.session_state is per-session, so a
# gate keyed on it can't stop 5 concurrent visitors from each triggering
# their own full-universe scan — see the "Run brief"/"Run screener" Cloud
# incident this was built to fix. A plain module-level dict is process-wide
# because Streamlit Cloud runs one Python process shared by every visitor.
# ---------------------------------------------------------------------------


def test_gate_state_defaults_not_processing_no_last_run() -> None:
    assert is_processing("some_never_used_gate_name") is False
    assert get_last_run_ts("some_never_used_gate_name") is None


def test_set_and_get_processing_round_trips() -> None:
    set_processing("test_gate_a", True)
    try:
        assert is_processing("test_gate_a") is True
    finally:
        set_processing("test_gate_a", False)
    assert is_processing("test_gate_a") is False


def test_set_and_get_last_run_ts_round_trips() -> None:
    set_last_run_ts("test_gate_b", 12345.0)
    assert get_last_run_ts("test_gate_b") == 12345.0


def test_gate_state_is_keyed_independently_per_name() -> None:
    """Home's gate and Screener's gate must not leak into each other."""
    set_processing("test_gate_home", True)
    set_processing("test_gate_screener", False)
    try:
        assert is_processing("test_gate_home") is True
        assert is_processing("test_gate_screener") is False
    finally:
        set_processing("test_gate_home", False)


def test_gate_state_shared_across_separate_reads() -> None:
    """The whole point: two independent call sites (simulating two different
    visitor sessions) observe the SAME state, unlike st.session_state."""
    set_processing("test_gate_shared", True)
    try:
        # A second, independent read (no shared object passed around) sees it.
        assert is_processing("test_gate_shared") is True
    finally:
        set_processing("test_gate_shared", False)
