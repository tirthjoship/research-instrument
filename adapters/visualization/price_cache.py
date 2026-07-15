"""Batch yfinance price fetching with TTL-cached Streamlit wrappers.

The `_impl` functions contain actual logic and can be called in any context.
The cached wrappers (e.g. `fetch_prices`) import streamlit at call time so the
module is safely importable in non-Streamlit contexts (CI, tests, CLI).
"""

from __future__ import annotations

import re
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


def _batch_fetch_closes_impl(
    tickers: tuple[str, ...], period: str = "3mo"
) -> dict[str, list[float]]:
    """Fetch full daily close series for multiple tickers via one yf.download() call.

    Returns ``{ticker: [close, close, ...]}`` (chronological). Cheaper than N
    separate ``_fetch_price_history_impl`` calls — one batched network round-trip
    for the whole group. Used for cross-price correlation (co-movement), where a
    ~3-month window is enough; unlike ``_batch_fetch_prices_impl`` this keeps the
    whole series, not just the last close.
    """
    if not tickers:
        return {}

    try:
        data = yf.download(
            list(tickers),
            period=period,
            auto_adjust=True,
            progress=False,
        )
    except Exception as exc:
        logger.warning("yf.download failed for {}: {}", tickers, exc)
        return {}

    if data is None or data.empty:
        return {}

    result: dict[str, list[float]] = {}

    if len(tickers) == 1:
        ticker = tickers[0]
        try:
            close_obj = data["Close"]
            if isinstance(close_obj, DataFrame):
                close_obj = (
                    close_obj[ticker]
                    if ticker in close_obj.columns
                    else close_obj.squeeze("columns")
                )
            closes = [float(c) for c in close_obj.dropna()]
            if closes:
                result[ticker] = closes
        except (KeyError, IndexError, TypeError) as exc:
            logger.warning("Could not extract closes for {}: {}", ticker, exc)
    else:
        try:
            close_df = data["Close"]
        except KeyError:
            logger.warning("No 'Close' column in yf.download result for {}", tickers)
            return {}

        for ticker in tickers:
            try:
                closes = [float(c) for c in close_df[ticker].dropna()]
                if closes:
                    result[ticker] = closes
            except (KeyError, IndexError) as exc:
                logger.warning("Could not extract closes for {}: {}", ticker, exc)

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
        records = cast(list[dict[str, Any]], df.to_dict(orient="records"))
        # yfinance 'Value' is unsigned and the consumers read lowercase 'value'.
        # Expose a signed 'value': disposals (Sale) reduce; awards/grants/
        # purchases accumulate. Direction is in the free-text 'Text' field.
        for r in records:
            raw = r.get("Value", r.get("value", 0)) or 0
            text = str(r.get("Text", "")).lower()
            sign = -1 if ("sale" in text or "dispos" in text) else 1
            r["value"] = sign * abs(float(raw))
        return records
    except Exception as exc:
        logger.warning("Insider transactions fetch failed for {}: {}", ticker, exc)
        return []


def _fetch_rating_distribution_impl(ticker: str) -> dict[str, int] | None:
    """Latest analyst rating distribution as numeric tiers 1..5 (1 = most positive).

    Maps yfinance recommendations_summary columns (strongBuy..strongSell) to
    forbidden-word-free keys r1..r5 so downstream view code stays slop-clean.
    Returns None on any error or empty data.
    """
    try:
        df = yf.Ticker(ticker).recommendations_summary
        if df is None or (hasattr(df, "empty") and df.empty):
            return None
        row = df.iloc[0]  # latest period (0m)
        cols = {
            "r1": "strongBuy",
            "r2": "buy",
            "r3": "hold",
            "r4": "sell",
            "r5": "strongSell",
        }
        out = {k: int(row.get(v, 0) or 0) for k, v in cols.items()}
        return out if sum(out.values()) > 0 else None
    except Exception as exc:
        logger.warning("Rating distribution fetch failed for {}: {}", ticker, exc)
        return None


def _fetch_annual_revenue_impl(ticker: str) -> list[float]:
    """Chronological annual Total Revenue (from yfinance income_stmt). [] on error."""
    try:
        df = yf.Ticker(ticker).income_stmt
        if df is None or df.empty or "Total Revenue" not in df.index:
            return []
        return list(
            reversed([float(v) for v in df.loc["Total Revenue"].values if v == v])
        )
    except Exception as exc:
        logger.warning("Annual revenue fetch failed for {}: {}", ticker, exc)
        return []


def _fetch_revenue_estimate_impl(ticker: str) -> float | None:
    """Forward (+1y) revenue growth estimate from yfinance revenue_estimate. None on error."""
    try:
        df = yf.Ticker(ticker).revenue_estimate
        if df is None or df.empty or "growth" not in df.columns:
            return None
        if "+1y" in df.index:
            g = df.loc["+1y", "growth"]
            return float(g) if g == g else None
        return None
    except Exception as exc:
        logger.warning("Revenue estimate fetch failed for {}: {}", ticker, exc)
        return None


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


def _extract_yfinance_news_url(
    item: dict[str, Any], content: dict[str, Any] | None
) -> str:
    """Pull an external article URL from a yfinance news payload."""
    blocks: list[Any] = []
    if isinstance(content, dict):
        blocks.extend(content.get(k) for k in ("clickThroughUrl", "canonicalUrl"))
    blocks.extend(item.get(k) for k in ("clickThroughUrl", "canonicalUrl", "link"))
    for block in blocks:
        if isinstance(block, dict):
            url = str(block.get("url") or "").strip()
            if url.startswith(("http://", "https://")):
                return url
        elif isinstance(block, str) and block.startswith(("http://", "https://")):
            return block.strip()
    return ""


def _parse_yfinance_news_item(item: dict[str, Any]) -> dict[str, str] | None:
    """Normalize one yfinance news item to {source, title, date, url}."""
    content = item.get("content")
    if isinstance(content, dict):
        title = str(content.get("title") or "").strip()
        pub = str(content.get("pubDate") or content.get("displayTime") or "")
        provider = content.get("provider")
        source = (
            str(provider.get("displayName") or "news")
            if isinstance(provider, dict)
            else "news"
        )
        url = _extract_yfinance_news_url(item, content)
    else:
        title = str(item.get("title") or "").strip()
        pub = str(item.get("providerPublishTime") or item.get("pubDate") or "")
        source = str(item.get("publisher") or item.get("publisherName") or "news")
        url = _extract_yfinance_news_url(item, None)
    if not title:
        return None
    return {"source": source, "title": title, "date": pub.strip(), "url": url}


_OTHER_TICKER_RE = re.compile(r"\(([A-Z]{1,5}(?:\.[A-Z])?)\)")


def _headline_is_about_other_ticker(title: str, ticker: str) -> bool:
    """True when *title* names a different company's ticker in parentheses
    (e.g. "UBS Raises its Price Target on Astera Labs, Inc. (ALAB)") and never
    mentions *ticker* itself.

    yfinance's per-ticker ``.news`` endpoint mixes in Yahoo's general
    "trending" feed, not just headlines about the requested company — without
    this filter, an unrelated company's news gets attributed to the ticker
    being researched (e.g. ALAB news cited as evidence in NVDA's read).
    """
    other_tickers = set(_OTHER_TICKER_RE.findall(title))
    if not other_tickers:
        return False
    if ticker.upper() in other_tickers:
        return False
    return not re.search(rf"\b{re.escape(ticker)}\b", title, re.IGNORECASE)


def _fetch_recent_news_impl(ticker: str, limit: int = 8) -> list[dict[str, str]]:
    """Fetch recent attributed headlines for *ticker* via yfinance. Returns [] on error."""
    try:
        raw = yf.Ticker(ticker).news or []
    except Exception as exc:  # noqa: BLE001
        logger.warning("yfinance news failed for {}: {}", ticker, exc)
        return []
    out: list[dict[str, str]] = []
    for item in raw:
        if not isinstance(item, dict):
            continue
        parsed = _parse_yfinance_news_item(item)
        if parsed is None:
            continue
        if _headline_is_about_other_ticker(parsed["title"], ticker):
            continue
        out.append(parsed)
        if len(out) >= limit:
            break
    return out
