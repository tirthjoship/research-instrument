"""Tests for the Lazy Prices wiring helpers. Pure + injected fakes — no live SEC/yfinance."""

from __future__ import annotations

from datetime import date, datetime
from pathlib import Path

from adapters.data.sec_filing_text_adapter import FilingRef
from application.lazy_prices_runner import (
    build_forward_excess_return_fn,
    build_similarity_fn,
    build_universe_fn,
    quarterly_cohorts,
    select_filing_pair,
)


def _ref(form: str, filed: str, fiscal: str, accn: str = "a") -> FilingRef:
    return FilingRef(
        ticker="NVDA",
        cik=1045810,
        form=form,
        filed_date=date.fromisoformat(filed),
        fiscal_period=fiscal,
        accession_nodash=accn,
        primary_doc=f"{accn}.htm",
    )


# --- quarterly_cohorts -------------------------------------------------------


def test_quarterly_cohorts_count_and_anchoring() -> None:
    cohorts = quarterly_cohorts(datetime(2015, 1, 1), datetime(2024, 12, 31))
    # 10 years x 4 quarters = 40 cohorts, each anchored to a quarter-start month.
    assert len(cohorts) == 40
    assert cohorts[0] == datetime(2015, 1, 1)
    assert cohorts[-1] == datetime(2024, 10, 1)
    assert all(c.month in (1, 4, 7, 10) and c.day == 1 for c in cohorts)


def test_quarterly_cohorts_snaps_start_into_quarter_grid() -> None:
    # A mid-quarter start snaps forward to the next quarter boundary within range.
    cohorts = quarterly_cohorts(datetime(2015, 2, 15), datetime(2015, 12, 31))
    assert cohorts == [
        datetime(2015, 4, 1),
        datetime(2015, 7, 1),
        datetime(2015, 10, 1),
    ]


# --- select_filing_pair ------------------------------------------------------


def test_select_pair_picks_latest_and_same_quarter_prior_year() -> None:
    filings = [
        _ref("10-Q", "2021-08-20", "2021-07-31", "q3_2021"),
        _ref("10-Q", "2022-05-10", "2022-04-30", "q1_2022"),  # adjacent quarter — wrong
        _ref("10-Q", "2022-08-22", "2022-07-31", "q3_2022"),  # current
    ]
    pair = select_filing_pair(filings, datetime(2022, 10, 1))
    assert pair is not None
    current, prior = pair
    assert current.accession_nodash == "q3_2022"
    # Prior comparable is the SAME fiscal quarter a year earlier, not the adjacent Q1.
    assert prior.accession_nodash == "q3_2021"


def test_select_pair_matches_form_10k_to_10k() -> None:
    filings = [
        _ref("10-K", "2021-02-24", "2021-01-29", "k_2021"),
        _ref("10-Q", "2021-08-20", "2021-07-31", "q3_2021"),
        _ref("10-K", "2022-02-24", "2022-01-29", "k_2022"),  # current
    ]
    pair = select_filing_pair(filings, datetime(2022, 6, 1))
    assert pair is not None
    current, prior = pair
    assert current.form == "10-K" and prior.form == "10-K"
    assert prior.accession_nodash == "k_2021"


def test_select_pair_excludes_filings_on_or_after_cohort() -> None:
    filings = [
        _ref("10-K", "2021-02-24", "2021-01-29", "k_2021"),
        _ref("10-K", "2022-02-24", "2022-01-29", "k_2022"),
        _ref("10-K", "2023-02-24", "2023-01-29", "k_2023"),  # after cohort — hidden
    ]
    pair = select_filing_pair(filings, datetime(2022, 6, 1))
    assert pair is not None
    current, prior = pair
    assert current.accession_nodash == "k_2022"  # NOT k_2023 (future)
    assert prior.accession_nodash == "k_2021"


def test_select_pair_none_when_no_comparable() -> None:
    assert select_filing_pair([], datetime(2022, 6, 1)) is None
    one = [_ref("10-K", "2022-02-24", "2022-01-29")]
    assert select_filing_pair(one, datetime(2022, 6, 1)) is None
    # Two filings but different forms => no same-form comparable.
    mixed = [
        _ref("10-K", "2021-02-24", "2021-01-29"),
        _ref("10-Q", "2022-05-10", "2022-04-30"),
    ]
    assert select_filing_pair(mixed, datetime(2022, 6, 1)) is None


# --- build_universe_fn -------------------------------------------------------


def test_build_universe_fn_returns_static_list(tmp_path: Path) -> None:
    f = tmp_path / "u.txt"
    f.write_text("# header\nNVDA\nAAPL\nNVDA\n")
    universe_fn = build_universe_fn([f])
    # Deduped, sorted, and identical regardless of the cohort date (survivor universe).
    assert universe_fn(datetime(2015, 1, 1)) == ["AAPL", "NVDA"]
    assert universe_fn(datetime(2024, 1, 1)) == ["AAPL", "NVDA"]


# --- build_forward_excess_return_fn ------------------------------------------


def test_forward_excess_return_subtracts_benchmark() -> None:
    series = {
        # ticker: +20% over the window; SPY: +5% => excess +15%.
        "NVDA": [(datetime(2022, 1, 1), 100.0), (datetime(2022, 4, 30), 120.0)],
        "SPY": [(datetime(2022, 1, 1), 400.0), (datetime(2022, 4, 30), 420.0)],
    }
    fn = build_forward_excess_return_fn(lambda t: series[t], horizon_days=63)
    excess = fn("NVDA", datetime(2022, 1, 1))
    assert abs(excess - 0.15) < 1e-9


# --- build_similarity_fn -----------------------------------------------------


def test_similarity_fn_wires_resolve_list_fetch_and_diff() -> None:
    cur = _ref("10-K", "2022-02-24", "2022-01-29", "k_2022")
    pri = _ref("10-K", "2021-02-24", "2021-01-29", "k_2021")
    sections = {
        "k_2022": {"risk_factors": "competition and regulatory risk in key markets"},
        "k_2021": {"risk_factors": "competition and regulatory risk in key markets"},
    }
    fn = build_similarity_fn(
        list_filings_fn=lambda tkr, cik, as_of: [pri, cur],
        fetch_sections_fn=lambda ref: sections[ref.accession_nodash],
        cik_resolve_fn=lambda tkr: 1045810,
    )
    score = fn("NVDA", datetime(2022, 6, 1))
    assert score is not None and score > 0.99  # identical sections => non-changer


def test_similarity_fn_none_on_unknown_cik() -> None:
    fn = build_similarity_fn(
        list_filings_fn=lambda *a: [],
        fetch_sections_fn=lambda ref: {},
        cik_resolve_fn=lambda tkr: None,
    )
    assert fn("ZZZZ", datetime(2022, 6, 1)) is None


def test_similarity_fn_none_when_no_pair() -> None:
    only = _ref("10-K", "2022-02-24", "2022-01-29", "k_2022")
    fn = build_similarity_fn(
        list_filings_fn=lambda *a: [only],
        fetch_sections_fn=lambda ref: {"risk_factors": "text"},
        cik_resolve_fn=lambda tkr: 1045810,
    )
    assert fn("NVDA", datetime(2022, 6, 1)) is None
