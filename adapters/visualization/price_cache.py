"""Batch yfinance price fetching with TTL-cached Streamlit wrappers.

The `_impl` functions contain actual logic and can be called in any context.
The cached wrappers (e.g. `fetch_prices`) import streamlit at call time so the
module is safely importable in non-Streamlit contexts (CI, tests, CLI).
"""

from __future__ import annotations

from datetime import datetime, time
from typing import Any, cast
from zoneinfo import ZoneInfo

import yfinance as yf
from loguru import logger
from pandas import DataFrame

ET = ZoneInfo("America/New_York")

_INDEX_TICKERS = ("SPY", "QQQ", "DIA", "IWM")

_MARKET_OPEN = time(9, 30)
_MARKET_CLOSE = time(16, 0)

# TTL in seconds for @st.cache_data
_TTL_MARKET_HOURS = 15 * 60
_TTL_AFTER_HOURS = 60 * 60


def _is_market_hours() -> bool:
    """Return True if current time falls within 09:30–16:00 ET."""
    now_et = datetime.now(tz=ET)
    t = now_et.time()
    return _MARKET_OPEN <= t < _MARKET_CLOSE


def _current_ttl() -> int:
    """Return TTL in seconds based on whether market is open."""
    return _TTL_MARKET_HOURS if _is_market_hours() else _TTL_AFTER_HOURS


# ---------------------------------------------------------------------------
# Implementation functions — import-safe, test-friendly
# ---------------------------------------------------------------------------


def _batch_fetch_prices_impl(tickers: tuple[str, ...]) -> dict[str, dict[str, float]]:
    """Fetch close prices for multiple tickers via yf.download().

    Returns ``{ticker: {"price": float, "change_pct": float}}``.
    Handles yfinance's different column shapes for single vs multi-ticker downloads.
    """
    if not tickers:
        return {}

    try:
        data = yf.download(
            list(tickers),
            period="5d",
            auto_adjust=True,
            progress=False,
        )
    except Exception as exc:
        logger.warning("yf.download failed for {}: {}", tickers, exc)
        return {}

    if data is None or data.empty:
        return {}

    result: dict[str, dict[str, float]] = {}

    if len(tickers) == 1:
        # Older yfinance: flat columns (data["Close"] is a Series). Newer
        # yfinance returns MultiIndex columns even for one ticker, making
        # data["Close"] a one-column DataFrame — squeeze it back to a Series.
        ticker = tickers[0]
        try:
            close_obj = data["Close"]
            if isinstance(close_obj, DataFrame):
                close_obj = (
                    close_obj[ticker]
                    if ticker in close_obj.columns
                    else close_obj.squeeze("columns")
                )
            close_series = close_obj.dropna()
            if len(close_series) < 2:
                return {}
            last = float(close_series.iloc[-1])
            prev = float(close_series.iloc[-2])
            change_pct = (last - prev) / prev * 100 if prev != 0 else 0.0
            result[ticker] = {"price": last, "change_pct": change_pct}
        except (KeyError, IndexError, TypeError) as exc:
            logger.warning("Could not extract price for {}: {}", ticker, exc)
    else:
        # MultiIndex columns: data["Close"][ticker]
        try:
            close_df = data["Close"]
        except KeyError:
            logger.warning("No 'Close' column in yf.download result for {}", tickers)
            return {}

        for ticker in tickers:
            try:
                series = close_df[ticker].dropna()
                if len(series) < 2:
                    continue
                last = float(series.iloc[-1])
                prev = float(series.iloc[-2])
                change_pct = (last - prev) / prev * 100 if prev != 0 else 0.0
                result[ticker] = {"price": last, "change_pct": change_pct}
            except (KeyError, IndexError) as exc:
                logger.warning("Could not extract price for {}: {}", ticker, exc)

    return result


def _fetch_ticker_info_impl(ticker: str) -> dict[str, Any]:
    """Fetch full ticker info dict from yfinance. Returns {} on any error."""
    try:
        t = yf.Ticker(ticker)
        return dict(t.info)
    except Exception as exc:
        logger.warning("yf.Ticker({}).info failed: {}", ticker, exc)
        return {}


def _fetch_quarterly_financials_impl(
    ticker: str,
) -> tuple[DataFrame | None, DataFrame | None, DataFrame | None]:
    """Return (income_stmt, balance_sheet, cashflow) quarterly DataFrames.

    Each can be None if unavailable.
    """
    try:
        t = yf.Ticker(ticker)
        income = t.quarterly_income_stmt
        balance = t.quarterly_balance_sheet
        cashflow = t.quarterly_cashflow
        return (
            income if income is not None and not income.empty else None,
            balance if balance is not None and not balance.empty else None,
            cashflow if cashflow is not None and not cashflow.empty else None,
        )
    except Exception as exc:
        logger.warning("Quarterly financials fetch failed for {}: {}", ticker, exc)
        return None, None, None


def _fetch_insider_transactions_impl(ticker: str) -> list[dict[str, Any]]:
    """Fetch insider transactions for *ticker*. Returns [] on any error or no data."""
    try:
        t = yf.Ticker(ticker)
        df = t.insider_transactions
        if df is None or (hasattr(df, "empty") and df.empty):
            return []
        return cast(list[dict[str, Any]], df.to_dict(orient="records"))
    except Exception as exc:
        logger.warning("Insider transactions fetch failed for {}: {}", ticker, exc)
        return []


def _fetch_index_prices_impl() -> dict[str, dict[str, float]]:
    """Fetch prices for SPY, QQQ, DIA, IWM."""
    return _batch_fetch_prices_impl(_INDEX_TICKERS)


# ---------------------------------------------------------------------------
# Streamlit-cached wrappers — import st at call time
# ---------------------------------------------------------------------------


def fetch_prices(tickers: tuple[str, ...]) -> dict[str, dict[str, float]]:
    """Streamlit-cached wrapper around _batch_fetch_prices_impl."""
    import streamlit as st

    ttl = _current_ttl()

    @st.cache_data(ttl=ttl)
    def _cached(t: tuple[str, ...]) -> dict[str, dict[str, float]]:
        return _batch_fetch_prices_impl(t)

    return _cached(tickers)


def fetch_ticker_info(ticker: str) -> dict[str, Any]:
    """Streamlit-cached wrapper around _fetch_ticker_info_impl."""
    import streamlit as st

    @st.cache_data(ttl=_TTL_AFTER_HOURS)
    def _cached(t: str) -> dict[str, Any]:
        return _fetch_ticker_info_impl(t)

    return _cached(ticker)


def fetch_quarterly_financials(
    ticker: str,
) -> tuple[DataFrame | None, DataFrame | None, DataFrame | None]:
    """Streamlit-cached wrapper around _fetch_quarterly_financials_impl."""
    import streamlit as st

    @st.cache_data(ttl=_TTL_AFTER_HOURS)
    def _cached(
        t: str,
    ) -> tuple[DataFrame | None, DataFrame | None, DataFrame | None]:
        return _fetch_quarterly_financials_impl(t)

    return _cached(ticker)


def fetch_insider_transactions(ticker: str) -> list[dict[str, Any]]:
    """Streamlit-cached wrapper around _fetch_insider_transactions_impl."""
    import streamlit as st

    @st.cache_data(ttl=_TTL_AFTER_HOURS)
    def _cached(t: str) -> list[dict[str, Any]]:
        return _fetch_insider_transactions_impl(t)

    return _cached(ticker)


def batch_fetch_prices(tickers: tuple[str, ...]) -> dict[str, dict[str, float]]:
    """Alias for fetch_prices — batch fetch prices for a tuple of tickers."""
    return fetch_prices(tickers)


# ---------------------------------------------------------------------------
# Price-history (closes / ATR / MA200) — impl + cached wrapper
# ---------------------------------------------------------------------------

_PRICE_HISTORY_TTL = 60 * 60  # 1 h — history moves slowly


def parse_price_history(df: DataFrame | None) -> dict[str, Any] | None:
    """Parse a yfinance history DataFrame into a prices dict (pure, no network).

    Returns a dict with keys:
      closes  - list[float]  : daily close prices (full 1-year window)
      ma200   - float | None : mean of last 200 closes (or all if < 200)
      atr     - float | None : 14-period average true range proxy
      vs_spy  - None         : computed separately; placeholder here

    Returns None when ``df`` is None or has no rows.
    """
    if df is None or df is None:
        return None
    if not hasattr(df, "__len__") or len(df) == 0:
        return None
    try:
        close_col = df["Close"] if "Close" in df.columns else None
        if close_col is None or close_col.dropna().empty:
            return None
        closes_series = close_col.dropna()
        closes = [float(c) for c in closes_series]

        ma200: float | None = (
            float(sum(closes[-200:]) / len(closes[-200:])) if closes else None
        )

        # ATR proxy: use High-Low if available, else mean abs day-over-day diff
        atr: float | None = None
        if "High" in df.columns and "Low" in df.columns:
            high_col = df["High"].dropna()
            low_col = df["Low"].dropna()
            aligned = high_col.align(low_col, join="inner")
            hl_range = [
                float(hi - lo)
                for hi, lo in zip(aligned[0].iloc[-14:], aligned[1].iloc[-14:])
            ]
            if hl_range:
                atr = sum(hl_range) / len(hl_range)
        else:
            # abs diff of last 14 daily closes
            tail = closes[-15:]  # 14 diffs from 15 points
            if len(tail) >= 2:
                diffs = [abs(tail[i] - tail[i - 1]) for i in range(1, len(tail))]
                atr = sum(diffs) / len(diffs) if diffs else None

        return {"closes": closes, "ma200": ma200, "atr": atr, "vs_spy": None}
    except Exception as exc:  # noqa: BLE001 — malformed df → None
        logger.warning("parse_price_history failed: {}", exc)
        return None


def _fetch_price_history_impl(ticker: str) -> dict[str, Any] | None:
    """Fetch 1-year daily history for *ticker* and parse it. Returns None on error."""
    import yfinance as yf  # lazy import for CI safety

    try:
        df: DataFrame = yf.Ticker(ticker).history(period="2y")
    except Exception as exc:  # noqa: BLE001 — network/parse failures → None
        logger.warning("Price history fetch failed for {}: {}", ticker, exc)
        return None
    return parse_price_history(df)


def fetch_price_history(ticker: str) -> dict[str, Any] | None:
    """Streamlit-cached wrapper around _fetch_price_history_impl (mirrors fetch_ticker_info)."""
    import streamlit as st  # lazy import, CI-safe

    @st.cache_data(ttl=_PRICE_HISTORY_TTL, show_spinner=False)
    def _cached(t: str) -> dict[str, Any] | None:
        return _fetch_price_history_impl(t)

    return _cached(ticker)


def fetch_index_prices() -> dict[str, dict[str, float]]:
    """Streamlit-cached wrapper around _fetch_index_prices_impl."""
    import streamlit as st

    ttl = _current_ttl()

    @st.cache_data(ttl=ttl)
    def _cached() -> dict[str, dict[str, float]]:
        return _fetch_index_prices_impl()

    return _cached()
