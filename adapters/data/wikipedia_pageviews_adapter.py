"""Wikipedia pageviews adapter — honest attention-intensity series.

Wikimedia REST pageviews API: keyless, daily granularity, multi-year history.
Implements AttentionSeriesPort.
"""

from __future__ import annotations

import time
from datetime import datetime
from typing import Any, Callable, cast

import requests
from loguru import logger

from domain.exceptions import SourceThrottledError
from domain.models import AttentionPoint

_API = (
    "https://wikimedia.org/api/rest_v1/metrics/pageviews/per-article/"
    "en.wikipedia/all-access/all-agents/{article}/daily/{start}/{end}"
)
_HEADERS = {"User-Agent": "research-instrument/1.0 (research)"}


class WikipediaPageviewsAdapter:
    def __init__(
        self,
        article_map: dict[str, str] | None = None,
        throttle_s: float = 0.2,
        max_retries: int = 3,
        http_get: Callable[..., Any] | None = None,
        sleep: Callable[[float], None] | None = None,
    ) -> None:
        self._article_map = article_map or {}
        self._throttle_s = throttle_s
        self._max_retries = max_retries
        self._http_get: Callable[..., Any] = (
            http_get if http_get is not None else cast(Callable[..., Any], requests.get)
        )
        self._sleep: Callable[[float], None] = (
            sleep if sleep is not None else cast(Callable[[float], None], time.sleep)
        )

    def _throttle(self) -> None:
        self._sleep(self._throttle_s)

    def get_attention_series(
        self, ticker: str, start: datetime, end: datetime
    ) -> list[AttentionPoint]:
        article = self._article_map.get(ticker, ticker)
        url = _API.format(
            article=article.replace(" ", "_"),
            start=start.strftime("%Y%m%d"),
            end=end.strftime("%Y%m%d"),
        )
        for attempt in range(self._max_retries + 1):
            try:
                self._throttle()
                resp = self._http_get(url, headers=_HEADERS, timeout=15)
                resp.raise_for_status()
                items = resp.json().get("items", [])
                break
            except Exception as exc:  # noqa: BLE001
                msg = str(exc)
                if "429" in msg or "Too Many Requests" in msg:
                    if attempt < self._max_retries:
                        backoff = (
                            self._throttle_s * (2**attempt)
                            if self._throttle_s > 0
                            else 0.0
                        )
                        self._sleep(backoff)
                        continue
                    raise SourceThrottledError(
                        f"Wikipedia rate-limited (429) for {ticker}: {msg}"
                    ) from exc
                logger.warning("Wikipedia pageviews failed for {}: {}", ticker, exc)
                return []

        out: list[AttentionPoint] = []
        for it in items:
            try:
                ts = datetime.strptime(str(it["timestamp"]), "%Y%m%d%H")
                out.append(AttentionPoint(ticker, ts, float(it["views"]), "wikipedia"))
            except (KeyError, ValueError):
                continue
        return out
