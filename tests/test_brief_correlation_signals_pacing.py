"""_fetch_correlation_signals — paced ticker signal fetch for the weekly
brief's concentration/correlation graph.

Without pacing, _build_weekly_brief's correlation graph fires up to ~100
unpaced live yfinance history fetches (held_tickers + universe[:100]) in a
tight loop. Under Cloud's shared/rate-limited IP this is exactly the shape
of burst that trips Yahoo's rate limit and hangs the "Run brief"/CSV-upload
rebuild for many minutes — the same class of problem this whole Cloud
deploy scaling workstream targeted, just a spot that wasn't touched yet."""

from __future__ import annotations

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
