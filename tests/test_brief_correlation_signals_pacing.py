"""_fetch_correlation_signals — paced ticker signal fetch for the weekly
brief's concentration/correlation graph.

Without pacing, _build_weekly_brief's correlation graph fires up to ~100
unpaced live yfinance history fetches (held_tickers + universe[:100]) in a
tight loop. Under Cloud's shared/rate-limited IP this is exactly the shape
of burst that trips Yahoo's rate limit and hangs the "Run brief"/CSV-upload
rebuild for many minutes — the same class of problem this whole Cloud
deploy scaling workstream targeted, just a spot that wasn't touched yet."""

from __future__ import annotations

import json
from datetime import datetime, timezone

from application.cli.brief_commands import _fetch_correlation_signals


class _FakeMarketData:
    def __init__(self, fail_for: set[str] | None = None) -> None:
        self.calls: list[str] = []
        self._fail_for = fail_for or set()

    def get_signals(self, ticker: str, as_of: object) -> list[str]:
        self.calls.append(ticker)
        if ticker in self._fail_for:
            raise RuntimeError("yfinance rate-limited")
        return [f"signal-for-{ticker}"]


def test_paces_between_every_ticker() -> None:
    """N tickers -> N sleep calls, mirroring Home's needs-review fetcher pace
    (weekly_brief.py's _CASE_FETCH_PACE_S) so a burst of yfinance calls never
    fires back-to-back."""
    md = _FakeMarketData()
    sleep_calls: list[float] = []

    result = _fetch_correlation_signals(
        md,
        ["AAA", "BBB", "CCC"],
        datetime.now(timezone.utc),
        sleep=sleep_calls.append,
    )

    assert md.calls == ["AAA", "BBB", "CCC"]
    assert len(sleep_calls) == 3
    assert all(s > 0 for s in sleep_calls)
    assert result["AAA"] == ["signal-for-AAA"]


def test_per_ticker_failure_degrades_to_empty_list_not_raise() -> None:
    md = _FakeMarketData(fail_for={"BBB"})

    result = _fetch_correlation_signals(
        md, ["AAA", "BBB"], datetime.now(timezone.utc), sleep=lambda s: None
    )

    assert result["AAA"] == ["signal-for-AAA"]
    assert result["BBB"] == []


def test_empty_ticker_list_returns_empty_dict_no_sleep() -> None:
    md = _FakeMarketData()
    sleep_calls: list[float] = []

    result = _fetch_correlation_signals(
        md, [], datetime.now(timezone.utc), sleep=sleep_calls.append
    )

    assert result == {}
    assert sleep_calls == []


# ---------------------------------------------------------------------------
# progress_path — cross-process progress reporting. rebuild_weekly_brief_cached
# runs the CLI in a subprocess, so the parent Streamlit process can't observe
# per-ticker progress directly; writing a small JSON status file after each
# ticker is the seam that lets the UI show "12/45 (2 failed)" instead of only
# elapsed wall-clock seconds.
# ---------------------------------------------------------------------------


def test_progress_path_written_after_each_ticker(tmp_path) -> None:  # type: ignore[no-untyped-def]
    md = _FakeMarketData()
    progress_file = tmp_path / "progress.json"

    _fetch_correlation_signals(
        md,
        ["AAA", "BBB", "CCC"],
        datetime.now(timezone.utc),
        sleep=lambda s: None,
        progress_path=str(progress_file),
    )

    final = json.loads(progress_file.read_text())
    assert final == {
        "completed": 3,
        "total": 3,
        "succeeded": 3,
        "failed": 0,
        "failed_tickers": [],
        "last_ticker": "CCC",
    }


def test_progress_path_tracks_failed_tickers(tmp_path) -> None:  # type: ignore[no-untyped-def]
    md = _FakeMarketData(fail_for={"BBB"})
    progress_file = tmp_path / "progress.json"

    _fetch_correlation_signals(
        md,
        ["AAA", "BBB"],
        datetime.now(timezone.utc),
        sleep=lambda s: None,
        progress_path=str(progress_file),
    )

    final = json.loads(progress_file.read_text())
    assert final["succeeded"] == 1
    assert final["failed"] == 1
    assert final["failed_tickers"] == ["BBB"]


def test_progress_path_none_writes_nothing() -> None:
    """Default behaviour (no progress_path) must not attempt any file IO —
    the personal CLI dogfood path never passes this."""
    md = _FakeMarketData()

    result = _fetch_correlation_signals(
        md, ["AAA"], datetime.now(timezone.utc), sleep=lambda s: None
    )

    assert result["AAA"] == ["signal-for-AAA"]
