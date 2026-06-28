"""Tests for the evidence registry — the metric->research single source of truth."""

from __future__ import annotations

import pytest

from domain.evidence_registry import (
    EvidenceEntry,
    Verdict,
    all_keys,
    entries_by_verdict,
    get_evidence,
)


def test_get_evidence_returns_entry_for_known_key() -> None:
    e = get_evidence("systematic_share")
    assert e is not None
    assert e.label == "Systematic share"
    assert e.adr == "ADR-052"
    assert e.verdict is Verdict.RESEARCH_ONLY


def test_get_evidence_unknown_key_returns_none() -> None:
    assert get_evidence("does_not_exist") is None


def test_every_entry_is_fully_populated() -> None:
    """Each entry must carry meaning + caveat + verdict (the backing a UI needs)."""
    for key in all_keys():
        e = get_evidence(key)
        assert isinstance(e, EvidenceEntry)
        assert e.key == key
        assert e.label.strip()
        assert e.meaning.strip()
        assert e.caveat.strip()
        assert isinstance(e.verdict, Verdict)


def test_killed_signals_are_marked_falsified_with_adr() -> None:
    """Sentiment is honestly carried as FALSIFIED, citing the ADR that killed it."""
    e = get_evidence("sentiment_signal")
    assert e is not None
    assert e.verdict is Verdict.FALSIFIED
    assert e.adr == "ADR-044"
    assert "falsified" in e.caveat.lower()


def test_analyst_dispersion_is_honest_about_not_being_revision_drift() -> None:
    """The relabeled factor must warn it is dispersion, not revision drift."""
    e = get_evidence("factor_analyst_dispersion")
    assert e is not None
    assert "dispersion" in e.label.lower()
    assert "revision" in e.caveat.lower()  # explicitly warns it is NOT revision drift


def test_snapshot_factors_flagged_not_point_in_time() -> None:
    for key in ("factor_value", "factor_quality"):
        e = get_evidence(key)
        assert e is not None
        assert "snapshot" in e.caveat.lower()
        assert e.verdict is Verdict.RESEARCH_ONLY


def test_forward_pending_gate_present() -> None:
    e = get_evidence("discipline_gate")
    assert e is not None
    assert e.verdict is Verdict.FORWARD_PENDING
    assert e.adr == "ADR-048"


@pytest.mark.parametrize(
    "verdict",
    [
        Verdict.FALSIFIED,
        Verdict.RESEARCH_ONLY,
        Verdict.DESCRIPTIVE,
        Verdict.FORWARD_PENDING,
    ],
)
def test_entries_by_verdict_groups_for_know_dont_know_card(verdict: Verdict) -> None:
    entries = entries_by_verdict(verdict)
    assert all(e.verdict is verdict for e in entries)
    assert len(entries) >= 1  # each bucket powers a row of the Home knowledge card
