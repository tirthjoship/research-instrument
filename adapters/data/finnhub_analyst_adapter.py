"""Finnhub analyst upgrade/downgrade adapter — AnalystRatingsPort implementation."""

from __future__ import annotations

import os
from datetime import datetime

import requests
from loguru import logger

from domain.analyst import AnalystAction, AnalystRating

_FINNHUB_BASE_URL = "https://finnhub.io/api/v1/stock/upgrade-downgrade"


def parse_upgrade_downgrade(
    payload: list[dict],  # type: ignore[type-arg]
    since: datetime,
    until: datetime | None,
    source: str = "finnhub",
) -> list[AnalystRating]:
    """Pure helper: convert Finnhub upgrade-downgrade payload to AnalystRating list.

    Applies point-in-time filtering: drops items published before ``since`` or
    after ``until``. Skips entries with missing ``gradeTime``.

    Args:
        payload: Parsed JSON list from Finnhub upgrade-downgrade endpoint.
        since: Inclusive lower bound for publish datetime.
        until: Inclusive upper bound (point-in-time safe). None means no upper bound.
        source: Source label attached to each AnalystRating.

    Returns:
        List of AnalystRating objects, ordered as received.
    """
    action_map: dict[str, AnalystAction] = {
        "up": AnalystAction.UPGRADE,
        "down": AnalystAction.DOWNGRADE,
        "init": AnalystAction.INIT,
        "main": AnalystAction.MAINTAIN,
        "reit": AnalystAction.MAINTAIN,
    }
    out: list[AnalystRating] = []
    for item in payload:
        ts = item.get("gradeTime")
        if ts is None:
            continue
        published = datetime.fromtimestamp(int(ts))
        if published < since or (until is not None and published > until):
            continue
        fg = item.get("fromGrade")
        prior = str(fg) if fg else None
        action = action_map.get(
            str(item.get("action", "")).lower(), AnalystAction.MAINTAIN
        )
        out.append(
            AnalystRating(
                ticker=str(item.get("symbol", "")),
                firm=str(item.get("company", "")),
                rating=str(item.get("toGrade", "")),
                prior_rating=prior,
                action=action,
                price_target=None,
                published_at=published,
                source=source,
            )
        )
    return out


class FinnhubAnalystAdapter:
    """AnalystRatingsPort implementation using the Finnhub upgrade-downgrade API.

    Reads the API key from the ``FINNHUB_API_KEY`` environment variable or an
    explicit constructor argument. On any network, auth, or parse error the
    adapter logs a warning and returns an empty list — it never raises.

    Args:
        api_key: Finnhub API key. Falls back to ``FINNHUB_API_KEY`` env var.
    """

    def __init__(self, api_key: str | None = None) -> None:
        self._api_key: str | None = api_key or os.environ.get("FINNHUB_API_KEY")

    def get_rating_events(
        self,
        ticker: str,
        since: datetime,
        until: datetime | None = None,
    ) -> list[AnalystRating]:
        """Return analyst rating events for *ticker* published in [since, until].

        Fetches the Finnhub upgrade-downgrade endpoint and applies point-in-time
        filtering.

        Args:
            ticker: Stock ticker symbol (e.g. ``"AAPL"``).
            since: Inclusive start datetime.
            until: Inclusive end datetime (point-in-time bound). None = no upper bound.

        Returns:
            List of AnalystRating objects. Empty list on any error.
        """
        if not self._api_key:
            logger.warning("Finnhub: FINNHUB_API_KEY not set — returning []")
            return []

        params: dict[str, str] = {
            "symbol": ticker,
            "token": self._api_key,
        }

        try:
            response = requests.get(_FINNHUB_BASE_URL, params=params, timeout=15)
            response.raise_for_status()
            payload: object = response.json()
            if not isinstance(payload, list):
                logger.warning("Finnhub: unexpected response type for {}", ticker)
                return []
            return parse_upgrade_downgrade(payload, since, until)
        except requests.HTTPError as exc:
            status = exc.response.status_code if exc.response is not None else "?"
            logger.warning("Finnhub HTTP {} for ticker {}: {}", status, ticker, exc)
            return []
        except Exception as exc:  # noqa: BLE001
            logger.warning("Finnhub request failed for ticker {}: {}", ticker, exc)
            return []
