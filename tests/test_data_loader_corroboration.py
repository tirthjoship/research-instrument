# tests/test_data_loader_corroboration.py
"""Tests for corroboration data loader extension."""

from __future__ import annotations

from datetime import date

from domain.corroboration_models import Stance
from tests.fakes.corroboration_store_fake import (
    FAKE_CLAIM_BULLISH,
    FAKE_SNAPSHOT,
    FakeCorroborationStore,
)


def _make_view(ticker: str, claims=None, candidates=None, run_id=1):
    """Helper: build CorroborationTabView via the internal builder."""
    from adapters.visualization.data_loader import _build_corroboration_view

    store = FakeCorroborationStore(
        run_id=run_id,
        claims=[FAKE_CLAIM_BULLISH] if claims is None else claims,
        candidates=[FAKE_SNAPSHOT] if candidates is None else candidates,
    )
    return _build_corroboration_view(ticker=ticker, store=store)


def test_build_view_returns_view_for_known_ticker():
    view = _make_view("AAPL")
    assert view is not None
    assert view.ticker == "AAPL"
    assert len(view.claims) == 1


def test_build_view_filters_by_ticker():
    from domain.corroboration_models import HarvestedClaim

    other_claim = HarvestedClaim(
        source_name="X",
        ticker="MSFT",
        stance=Stance.BULLISH,
        thesis_summary="not for aapl",
        url="https://x.com",
        published_at=date(2026, 6, 1),
        verified=False,
        reliability_weight=0.5,
    )
    view = _make_view("AAPL", claims=[FAKE_CLAIM_BULLISH, other_claim])
    assert view is not None
    assert all(c.ticker == "AAPL" for c in view.claims)


def test_build_view_returns_none_when_no_run():
    from adapters.visualization.data_loader import _build_corroboration_view

    store = FakeCorroborationStore(run_id=None)
    assert _build_corroboration_view("AAPL", store) is None


def test_build_view_empty_claims_returns_view_with_empty_tuple():
    view = _make_view("AAPL", claims=[])
    assert view is not None
    assert view.claims == ()


def test_directional_views_bullish_majority():
    view = _make_view("AAPL", claims=[FAKE_CLAIM_BULLISH])
    assert view is not None
    assert len(view.directional_views) == 1
    assert view.directional_views[0].tilt in {"LEAN_IN", "HOLD"}


def test_load_corroboration_snapshot_returns_none_for_missing_db(tmp_path):
    from adapters.visualization.data_loader import load_corroboration_snapshot

    result = load_corroboration_snapshot("AAPL", db_path=str(tmp_path / "missing.db"))
    assert result is None


def test_load_corroboration_snapshot_handles_db_with_no_corroboration_tables(
    tmp_path, caplog
):
    """Reproduces the live-Cloud bug: a real, existing recommendations.db
    that has never had a corroboration harvest run against it (so the
    corroboration_runs table was never created — CorroborationStore.__init__
    doesn't create it; only init_schema() does, and every writer call site
    calls it, but load_corroboration_snapshot() didn't). Before the fix this
    raised sqlite3.OperationalError: no such table: corroboration_runs,
    swallowed into a logged warning on every single ticker load."""
    import sqlite3

    from adapters.visualization.data_loader import load_corroboration_snapshot

    db_path = tmp_path / "recommendations.db"
    conn = sqlite3.connect(str(db_path))
    conn.execute("CREATE TABLE recommendations (ticker TEXT)")  # unrelated table
    conn.commit()
    conn.close()

    with caplog.at_level("WARNING"):
        result = load_corroboration_snapshot("AAPL", db_path=str(db_path))

    assert result is None  # legitimately no run yet, not an error
    assert "corroboration snapshot load failed" not in caplog.text


def test_default_db_path_matches_where_corroborate_cli_writes():
    """The dashboard must read the same DB the `corroborate` CLI writes to.

    ``corroborate`` (application/cli/corroboration_commands.py) always connects
    to "data/recommendations.db" via CorroborationStore. If the dashboard's
    default db_path drifts from that, the Corroboration section silently shows
    the empty state forever, regardless of how much real data exists.
    """
    import inspect

    from adapters.visualization.data_loader import load_corroboration_snapshot

    sig = inspect.signature(load_corroboration_snapshot)
    assert sig.parameters["db_path"].default == "data/recommendations.db"
