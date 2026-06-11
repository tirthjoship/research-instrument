"""Per-run fetch health tally for the weekly job. Pure counters; the CLI reads
any_failed() to decide a loud non-zero exit. Collect-then-fail: the fetch loop
records every ticker's outcome and finishes ALL assessable names before the job
exits non-zero — one flaky fetch never aborts a 66-name run mid-loop."""

from __future__ import annotations


class FetchHealth:
    def __init__(self) -> None:
        self.ok = 0
        self.no_data = 0
        self.pruned = 0
        self.failed_tickers: list[str] = []

    def record_ok(self, ticker: str) -> None:
        self.ok += 1

    def record_no_data(self, ticker: str) -> None:
        self.no_data += 1

    def record_failed(self, ticker: str) -> None:
        self.failed_tickers.append(ticker)

    def record_pruned(self, ticker: str) -> None:
        self.pruned += 1

    def any_failed(self) -> bool:
        return len(self.failed_tickers) > 0

    def summary_line(self) -> str:
        return (
            f"fetched OK={self.ok} no-data={self.no_data} "
            f"FAILED={len(self.failed_tickers)} pruned={self.pruned}"
        )
