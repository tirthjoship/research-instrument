"""_build_weekly_brief() must read the published screen snapshot (item 5 of
the Cloud deploy scaling design) instead of running a live ~512-ticker scan
inline on every "Run brief" click.

_build_weekly_brief() wires ~10 unrelated subsystems (correlation graph,
macro-beta, sqlite forward-tracking, discipline log) that would need heavy
fakes just to reach the one screen-construction line under test here — this
repo already accepts a source-inspection regression guard for this shape of
change (see test_dashboard_smoke.py::test_app_title_uses_fraunces_not_dm_sans).
"""

from __future__ import annotations

import inspect

from application.cli import brief_commands


def test_build_weekly_brief_uses_snapshot_reader_not_live_scan() -> None:
    src = inspect.getsource(brief_commands._build_weekly_brief)
    assert "SnapshotScreenReader" in src, (
        "_build_weekly_brief must build a SnapshotScreenReader (reads the "
        "published screen_<date>.json) instead of running a live evidence "
        "screen inline on every visitor click."
    )
    assert "_build_evidence_screen(deps)" not in src, (
        "_build_weekly_brief must no longer call the live, full-universe "
        "_build_evidence_screen(deps) — that's what tripped Yahoo's burst "
        "rate-limit on the Cloud deploy."
    )


def test_snapshot_reader_scoped_to_the_brief_report_dir() -> None:
    """The reader must read from this brief's own report_dir (so sample vs.
    uploaded books, and any future per-book reports_dir, stay isolated)."""
    src = inspect.getsource(brief_commands._build_weekly_brief)
    assert "SnapshotScreenReader(report_dir)" in src
