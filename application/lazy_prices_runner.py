"""Wiring for the Lazy Prices (ADR-057) verdict run.

The ``LazyPricesBacktestUseCase`` is pure: it takes three injected callables
(``similarity_fn`` / ``forward_return_fn`` / ``universe_fn``) and orchestrates them. This module
builds those callables from real data sources, plus the pure helpers the run needs:

  * ``quarterly_cohorts`` — the rebalance dates (one filing season per quarter).
  * ``select_filing_pair`` — given a ticker's point-in-time filings, pick the current filing and
    its prior comparable (same form, ~1 fiscal year earlier) to diff.
  * ``build_universe_fn`` / ``build_forward_excess_return_fn`` / ``build_similarity_fn``.

Everything here is dependency-injected (callables passed in), so it is unit-tested with fakes and
never imports a live SEC/yfinance client itself — the CLI composition root supplies those.
"""

from __future__ import annotations

from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Callable

from adapters.data.sec_filing_text_adapter import FilingRef
from application.price_returns import compute_forward_return
from application.ticker_universe import load_ticker_universe
from domain.filing_textchange_service import textchange_similarity

# Type aliases for the injected callables (read top-to-bottom as the data flow).
SeriesFn = Callable[[str], list[tuple[datetime, float]]]
ListFilingsFn = Callable[[str, int, date], list[FilingRef]]
FetchSectionsFn = Callable[[FilingRef], dict[str, str]]
CikResolveFn = Callable[[str], int | None]


def quarterly_cohorts(start: datetime, end: datetime) -> list[datetime]:
    """Quarterly cohort dates (1st of Jan/Apr/Jul/Oct) over [start, end] inclusive.

    Quarterly cadence (not annual) is deliberate — ADR-057 maximises cohort count to tighten the
    IC confidence interval. Anchored to calendar quarters; the caller trims ``end`` so every
    cohort still has a full forward horizon of price data.
    """
    cohorts: list[datetime] = []
    year = start.year
    month = ((start.month - 1) // 3) * 3 + 1  # snap to quarter start: 1,4,7,10
    d = datetime(year, month, 1)
    while d < start:
        d = _next_quarter(d)
    while d <= end:
        cohorts.append(d)
        d = _next_quarter(d)
    return cohorts


def _next_quarter(d: datetime) -> datetime:
    m = d.month + 3
    return datetime(d.year + (m - 1) // 12, (m - 1) % 12 + 1, 1)


def _parse_fiscal(period: str) -> date | None:
    try:
        return date.fromisoformat(period)
    except (ValueError, TypeError):
        return None


def select_filing_pair(
    filings: list[FilingRef], cohort_date: datetime
) -> tuple[FilingRef, FilingRef] | None:
    """Pick (current, prior_comparable) from a ticker's point-in-time filings.

    ``current`` = the most recent filing filed strictly before ``cohort_date`` (no intraday leak).
    ``prior_comparable`` = the same-form filing one fiscal year earlier — matched on ``fiscal_period``
    when parseable (so a 10-Q is paired with the same quarter a year prior, not an adjacent
    quarter), else by the filing whose date is closest to one year before ``current``.

    Returns ``None`` when there is no usable pair (no comparable) — the caller then drops the
    event (MISSING, never imputed), matching the coverage discipline.
    """
    cutoff = cohort_date.date()
    before = [f for f in filings if f.filed_date < cutoff]
    if len(before) < 2:
        return None
    current = max(before, key=lambda f: f.filed_date)
    candidates = [
        f
        for f in before
        if f.form == current.form and f.filed_date < current.filed_date
    ]
    if not candidates:
        return None

    cur_fp = _parse_fiscal(current.fiscal_period)
    if cur_fp is not None:
        target = cur_fp - timedelta(days=365)

        def fp_distance(f: FilingRef) -> int:
            fp = _parse_fiscal(f.fiscal_period)
            if fp is None:
                return 10_000  # de-prioritise unparseable against a real fiscal match
            return abs((fp - target).days)

        prior = min(candidates, key=fp_distance)
    else:
        target_filed = current.filed_date - timedelta(days=365)
        prior = min(candidates, key=lambda f: abs((f.filed_date - target_filed).days))
    return current, prior


def build_universe_fn(ticker_files: list[Path]) -> Callable[[datetime], list[str]]:
    """Static survivor universe (ADR-057 §2 decision): the same current S&P500 ∪ NASDAQ-100 list
    at every cohort. The date argument is accepted (the port shape) but intentionally ignored.
    """
    tickers = load_ticker_universe(ticker_files)

    def universe_fn(_cohort: datetime) -> list[str]:
        return tickers

    return universe_fn


def build_forward_excess_return_fn(
    series_fn: SeriesFn,
    horizon_days: int,
    benchmark: str = "SPY",
) -> Callable[[str, datetime], float]:
    """Forward EXCESS return = ticker return − benchmark return over ``horizon_days``.

    Both legs use ``compute_forward_return`` (point-in-time: entry = last close ≤ cohort, exit =
    first close ≥ cohort+horizon). Missing price data yields 0.0 per that helper's contract — rare
    on this liquid universe, and such names are usually already dropped via a MISSING similarity.
    """

    def forward_return_fn(ticker: str, cohort_date: datetime) -> float:
        tkr = compute_forward_return(series_fn(ticker), cohort_date, horizon_days)
        bench = compute_forward_return(series_fn(benchmark), cohort_date, horizon_days)
        return tkr - bench

    return forward_return_fn


def build_similarity_fn(
    list_filings_fn: ListFilingsFn,
    fetch_sections_fn: FetchSectionsFn,
    cik_resolve_fn: CikResolveFn,
    lookback_days: int = 1,
) -> Callable[[str, datetime], float | None]:
    """Text-change similarity of a ticker's current filing vs its prior comparable, as of a cohort.

    Returns ``None`` (MISSING, dropped) when the CIK is unknown, there is no comparable filing
    pair, or no informative section overlaps both filings.
    """

    def similarity_fn(ticker: str, cohort_date: datetime) -> float | None:
        cik = cik_resolve_fn(ticker)
        if cik is None:
            return None
        as_of = (cohort_date - timedelta(days=lookback_days)).date()
        filings = list_filings_fn(ticker, cik, as_of)
        pair = select_filing_pair(filings, cohort_date)
        if pair is None:
            return None
        current, prior = pair
        return textchange_similarity(
            fetch_sections_fn(current), fetch_sections_fn(prior)
        )

    return similarity_fn
