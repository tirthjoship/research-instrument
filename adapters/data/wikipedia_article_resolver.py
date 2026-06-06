"""Wikipedia article resolver — resolves a company name to its Wikipedia article title
and validates the article by pageview volume to reject stubs and disambiguation pages.

A genuine company article typically receives hundreds to thousands of views per day; a
wrong stub or disambiguation page gets single digits.  Mean daily views >= min_views
(default 50) is used as the acceptance gate.
"""

from __future__ import annotations

import time
from datetime import datetime
from typing import Any, Callable, cast
from urllib.parse import quote

import requests
from loguru import logger

_OPENSEARCH = (
    "https://en.wikipedia.org/w/api.php"
    "?action=opensearch&search={name}&limit=1&namespace=0&format=json"
)
_PAGEVIEWS = (
    "https://wikimedia.org/api/rest_v1/metrics/pageviews/per-article/"
    "en.wikipedia/all-access/all-agents/{article}/daily/{start}/{end}"
)
_HEADERS = {"User-Agent": "multi-modal-stock-recommender/1.0 (research)"}


class WikipediaArticleResolver:
    """Resolves a company name to its Wikipedia article title via OpenSearch,
    then optionally validates the article by mean daily pageview volume."""

    def __init__(
        self,
        throttle_s: float = 0.0,
        http_get: Callable[..., Any] | None = None,
        sleep: Callable[[float], None] | None = None,
    ) -> None:
        self._throttle_s = throttle_s
        self._http_get: Callable[..., Any] = (
            http_get if http_get is not None else cast(Callable[..., Any], requests.get)
        )
        self._sleep: Callable[[float], None] = (
            sleep if sleep is not None else cast(Callable[[float], None], time.sleep)
        )

    def _throttle(self) -> None:
        self._sleep(self._throttle_s)

    def resolve(self, name: str) -> str | None:
        """Return the best Wikipedia article title for *name*, or None on miss/error."""
        encoded = quote(name, safe="")
        url = _OPENSEARCH.format(name=encoded)
        try:
            self._throttle()
            resp = self._http_get(url, headers=_HEADERS, timeout=15)
            resp.raise_for_status()
            data = resp.json()
            titles: list[str] = data[1]
            if not titles:
                return None
            return titles[0]
        except Exception as exc:  # noqa: BLE001
            logger.warning(
                "WikipediaArticleResolver.resolve failed for {}: {}", name, exc
            )
            return None

    def mean_daily_views(self, article: str, start: datetime, end: datetime) -> float:
        """Return mean daily pageviews for *article* over [start, end], or 0.0 on miss/error."""
        safe_article = quote(article.replace(" ", "_"), safe="")
        url = _PAGEVIEWS.format(
            article=safe_article,
            start=start.strftime("%Y%m%d"),
            end=end.strftime("%Y%m%d"),
        )
        try:
            self._throttle()
            resp = self._http_get(url, headers=_HEADERS, timeout=15)
            resp.raise_for_status()
            items = resp.json().get("items", [])
            if not items:
                return 0.0
            vals = [
                float(it["views"])
                for it in items
                if isinstance(it, dict) and "views" in it
            ]
            if not vals:
                return 0.0
            return sum(vals) / len(vals)
        except Exception as exc:  # noqa: BLE001
            logger.warning(
                "WikipediaArticleResolver.mean_daily_views failed for {}: {}",
                article,
                exc,
            )
            return 0.0

    def resolve_validated(
        self,
        name: str,
        start: datetime,
        end: datetime,
        min_views: float = 50.0,
    ) -> str | None:
        """Resolve *name* to an article title and accept it only if mean daily views >= min_views.

        Returns the article title on acceptance, None on miss or rejection.
        """
        art = self.resolve(name)
        if art is None:
            return None
        if self.mean_daily_views(art, start, end) >= min_views:
            return art
        return None
