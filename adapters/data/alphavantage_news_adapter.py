"""Alpha Vantage news headline adapter — NewsHeadlinePort implementation."""

from __future__ import annotations

import os
from datetime import datetime

import requests
from loguru import logger

_AV_BASE_URL = "https://www.alphavantage.co/query"


def parse_news_feed(
    payload: dict[str, object],
    since: datetime,
    until: datetime | None,
) -> list[tuple[str, str]]:
    """Pure helper: convert Alpha Vantage NEWS_SENTIMENT payload to [(title, YYYY-MM-DD)].

    Applies point-in-time filtering: drops items published before `since` or
    after `until`. Skips entries with missing / unparseable `time_published`.

    Args:
        payload: Parsed JSON response from Alpha Vantage NEWS_SENTIMENT endpoint.
        since: Inclusive lower bound for publish datetime.
        until: Inclusive upper bound (point-in-time safe). None means no upper bound.

    Returns:
        List of (headline, "YYYY-MM-DD") tuples, ordered as received.
    """
    feed = payload.get("feed")
    if not isinstance(feed, list):
        return []

    results: list[tuple[str, str]] = []
    for item in feed:
        if not isinstance(item, dict):
            continue
        title = item.get("title")
        time_published = item.get("time_published")
        if not isinstance(title, str) or not isinstance(time_published, str):
            continue
        try:
            # AV format: "YYYYMMDDTHHMMSS"
            pub_dt = datetime.strptime(time_published, "%Y%m%dT%H%M%S")
        except ValueError as exc:
            logger.warning(
                "AlphaVantage: skipping malformed time_published {!r}: {}",
                time_published,
                exc,
            )
            continue

        if pub_dt < since:
            continue
        if until is not None and pub_dt > until:
            continue

        results.append((title, pub_dt.strftime("%Y-%m-%d")))

    return results


class AlphaVantageNewsAdapter:
    """NewsHeadlinePort implementation using the Alpha Vantage NEWS_SENTIMENT API.

    Reads the API key from the ``ALPHAVANTAGE_API_KEY`` environment variable or
    an explicit constructor argument. On any network, auth, or parse error the
    adapter logs a warning and returns an empty list — it never raises.

    Args:
        api_key: Alpha Vantage API key. Falls back to ``ALPHAVANTAGE_API_KEY`` env var.
    """

    def __init__(self, api_key: str | None = None) -> None:
        self._api_key: str | None = api_key or os.environ.get("ALPHAVANTAGE_API_KEY")

    def get_recent_headlines(
        self,
        ticker: str,
        since: datetime,
        until: datetime | None = None,
    ) -> list[tuple[str, str]]:
        """Return recent headlines for *ticker* published in [since, until].

        Fetches the Alpha Vantage NEWS_SENTIMENT endpoint, converts the
        ``time_published`` field from ``YYYYMMDDTHHMMSS`` to ``YYYY-MM-DD``,
        and applies point-in-time filtering.

        Args:
            ticker: Stock ticker symbol (e.g. ``"AAPL"``).
            since: Inclusive start datetime.
            until: Inclusive end datetime (point-in-time bound). None = no upper bound.

        Returns:
            List of ``(headline, "YYYY-MM-DD")`` tuples. Empty list on any error.
        """
        if not self._api_key:
            logger.warning("AlphaVantage: ALPHAVANTAGE_API_KEY not set — returning []")
            return []

        params: dict[str, str] = {
            "function": "NEWS_SENTIMENT",
            "tickers": ticker,
            "time_from": since.strftime("%Y%m%dT%H%M"),
            "apikey": self._api_key,
        }

        try:
            response = requests.get(_AV_BASE_URL, params=params, timeout=15)
            response.raise_for_status()
            payload: object = response.json()
            if not isinstance(payload, dict):
                logger.warning("AlphaVantage: unexpected response type for {}", ticker)
                return []
            return parse_news_feed(payload, since, until)
        except requests.HTTPError as exc:
            status = exc.response.status_code if exc.response is not None else "?"
            logger.warning(
                "AlphaVantage HTTP {} for ticker {}: {}", status, ticker, exc
            )
            return []
        except Exception as exc:  # noqa: BLE001
            logger.warning("AlphaVantage request failed for ticker {}: {}", ticker, exc)
            return []
