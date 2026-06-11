"""Forward-return computation for the conviction backtest. Pure + a yfinance loader."""

from __future__ import annotations

import time as _time
from datetime import datetime, timedelta

from adapters.data.retry import retry_with_backoff
from domain.exceptions import PriceFetchError

_SLEEP = _time.sleep  # module-level seam so tests can stub backoff waits


def compute_forward_return(
    series: list[tuple[datetime, float]], entry_date: datetime, horizon_days: int
) -> float:
    """Realized return from the last close on/before entry_date to the first close
    on/after entry_date+horizon_days. Returns 0.0 if either point is unavailable.
    `series` must be ascending by date."""
    entry_price = None
    for d, c in series:
        if d <= entry_date:
            entry_price = c
        else:
            break
    if entry_price is None or entry_price == 0:
        return 0.0
    exit_target = entry_date + timedelta(days=horizon_days)
    exit_price = None
    for d, c in series:
        if d >= exit_target:
            exit_price = c
            break
    if exit_price is None:
        return 0.0
    return (exit_price - entry_price) / entry_price


def _fetch_history(
    ticker: str, start: datetime, end: datetime
) -> list[tuple[datetime, float]]:
    """Raw yfinance fetch. Returns ascending (date, close); [] if the symbol
    has no rows in range. Raises on a genuine fetch error (network, etc.)."""
    import yfinance as yf

    df = yf.Ticker(ticker).history(
        start=start.strftime("%Y-%m-%d"), end=end.strftime("%Y-%m-%d")
    )
    if df is None or df.empty:
        return []
    out: list[tuple[datetime, float]] = []
    for idx, row in df.iterrows():
        out.append((idx.to_pydatetime().replace(tzinfo=None), float(row["Close"])))
    return out


def load_price_series(
    ticker: str,
    start: datetime,
    end: datetime,
    *,
    strict: bool = False,
) -> list[tuple[datetime, float]]:
    """Load (date, close) ascending from yfinance, with retry/backoff.

    Tri-state:
      - rows in range            -> the series
      - no rows (new/delisted)   -> []  (NOT an error, both modes)
      - fetch error after retries-> strict=False: log + []  (legacy contract,
                                     ~18 callers); strict=True: raise
                                     PriceFetchError(ticker).
    """
    try:
        return retry_with_backoff(
            lambda: _fetch_history(ticker, start, end), sleep=_SLEEP
        )
    except Exception as exc:
        if strict:
            raise PriceFetchError(ticker, cause=exc) from exc
        from loguru import logger

        logger.warning(f"price load failed for {ticker}: {exc}")
        return []
