"""Integration test for the `lazy-prices` CLI command. All network seams patched (rule #5)."""

from __future__ import annotations

import json
from datetime import date, datetime
from pathlib import Path
from unittest.mock import patch

from click.testing import CliRunner

from adapters.data.sec_filing_text_adapter import FilingRef
from application.cli import cli


def _filings(ticker: str, cik: int, as_of: date) -> list[FilingRef]:
    # Two same-form filings, both filed before any 2015 cohort -> a valid comparable pair.
    return [
        FilingRef(
            ticker, cik, "10-K", date(2013, 2, 20), "2013-01-29", "k13", "k13.htm"
        ),
        FilingRef(
            ticker, cik, "10-K", date(2014, 2, 20), "2014-01-29", "k14", "k14.htm"
        ),
    ]


def _sections(ref: FilingRef) -> dict[str, str]:
    # Near-identical across years -> a "non-changer" (high similarity), so coverage > 0.
    return {"risk_factors": "competition and regulatory risk in our key end markets"}


def _prices(
    ticker: str, start: datetime, end: datetime
) -> list[tuple[datetime, float]]:
    base = 100.0 if ticker != "SPY" else 400.0
    return [
        (datetime(2014, 12, 1), base),
        (datetime(2015, 6, 1), base * 1.10),
        (datetime(2015, 12, 1), base * 1.15),
        (datetime(2016, 6, 1), base * 1.20),
    ]


def test_lazy_prices_command_writes_report(tmp_path: Path) -> None:
    uni = tmp_path / "u.txt"
    uni.write_text("# universe\nAAA\nBBB\n")
    reports = tmp_path / "reports"
    cache = tmp_path / "cache"

    with (
        patch(
            "adapters.data.sec_cik_resolver.SECCikResolver.resolve", return_value=12345
        ),
        patch(
            "adapters.data.sec_filing_text_adapter.SECFilingTextAdapter.list_filings",
            side_effect=_filings,
        ),
        patch(
            "adapters.data.sec_filing_text_adapter.SECFilingTextAdapter.fetch_sections",
            side_effect=_sections,
        ),
        patch("application.price_returns.load_price_series", side_effect=_prices),
    ):
        result = CliRunner().invoke(
            cli,
            [
                "lazy-prices",
                "--start",
                "2015-01-01",
                "--end",
                "2015-12-31",
                "--report-dir",
                str(reports),
                "--cache-dir",
                str(cache),
                "--ticker-file",
                str(uni),
            ],
        )

    assert result.exit_code == 0, result.output
    written = list(reports.glob("lazy_prices_ic_63d_*.json"))
    assert len(written) == 1
    report = json.loads(written[0].read_text())
    # Structure + honest accounting present.
    assert report["adr"] == "057"
    assert report["universe_size"] == 2
    # 2 tickers x 4 quarterly cohorts, each with a usable similarity pair -> 8 events, full
    # coverage. With the methodology's min_names=50, no cohort qualifies for IC, so the locked
    # THIN_N guard fires — exactly the honest behavior on a tiny (smoke-sized) universe.
    assert report["n_events"] == 8
    assert report["coverage"] > 0.0
    assert report["verdict"] == "INCONCLUSIVE_THIN_N"
    # Section cache was written so the one-time fetch persists.
    assert (cache / "sections" / "k14.json").exists()


def test_lazy_prices_smoke_limit_caps_universe(tmp_path: Path) -> None:
    uni = tmp_path / "u.txt"
    uni.write_text("AAA\nBBB\nCCC\n")
    reports = tmp_path / "reports"

    with (
        patch("adapters.data.sec_cik_resolver.SECCikResolver.resolve", return_value=1),
        patch(
            "adapters.data.sec_filing_text_adapter.SECFilingTextAdapter.list_filings",
            side_effect=_filings,
        ),
        patch(
            "adapters.data.sec_filing_text_adapter.SECFilingTextAdapter.fetch_sections",
            side_effect=_sections,
        ),
        patch("application.price_returns.load_price_series", side_effect=_prices),
    ):
        result = CliRunner().invoke(
            cli,
            [
                "lazy-prices",
                "--start",
                "2015-01-01",
                "--end",
                "2015-06-30",
                "--report-dir",
                str(reports),
                "--cache-dir",
                str(tmp_path / "c"),
                "--ticker-file",
                str(uni),
                "--limit",
                "1",
            ],
        )

    assert result.exit_code == 0, result.output
    assert "SMOKE" in result.output
    report = json.loads(next(reports.glob("*.json")).read_text())
    assert report["universe_size"] == 1
    assert report["smoke_limit"] == 1


def test_lazy_prices_normalizes_dotted_ticker_for_yfinance(tmp_path: Path) -> None:
    """Class-share tickers (BRK.B) are fetched from yfinance as BRK-B, not BRK.B."""
    uni = tmp_path / "u.txt"
    uni.write_text("BRK.B\n")
    seen: list[str] = []

    def _capture_prices(
        ticker: str, start: datetime, end: datetime
    ) -> list[tuple[datetime, float]]:
        seen.append(ticker)
        return _prices(ticker, start, end)

    with (
        patch("adapters.data.sec_cik_resolver.SECCikResolver.resolve", return_value=1),
        patch(
            "adapters.data.sec_filing_text_adapter.SECFilingTextAdapter.list_filings",
            side_effect=_filings,
        ),
        patch(
            "adapters.data.sec_filing_text_adapter.SECFilingTextAdapter.fetch_sections",
            side_effect=_sections,
        ),
        patch(
            "application.price_returns.load_price_series", side_effect=_capture_prices
        ),
    ):
        result = CliRunner().invoke(
            cli,
            [
                "lazy-prices",
                "--start",
                "2015-01-01",
                "--end",
                "2015-06-30",
                "--report-dir",
                str(tmp_path / "r"),
                "--cache-dir",
                str(tmp_path / "c"),
                "--ticker-file",
                str(uni),
            ],
        )

    assert result.exit_code == 0, result.output
    assert "BRK-B" in seen  # normalised for yfinance
    assert "BRK.B" not in seen  # the dotted form was never sent to yfinance
