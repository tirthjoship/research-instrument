"""Wikipedia pageviews adapter — honest attention-intensity series.

Wikimedia REST pageviews API: keyless, daily granularity, multi-year history.
Implements AttentionSeriesPort.
"""

from __future__ import annotations

import time
from datetime import datetime

import requests
from loguru import logger

from domain.models import AttentionPoint

_API = (
    "https://wikimedia.org/api/rest_v1/metrics/pageviews/per-article/"
    "en.wikipedia/all-access/all-agents/{article}/daily/{start}/{end}"
)
_HEADERS = {"User-Agent": "multi-modal-stock-recommender/1.0 (research)"}


class WikipediaPageviewsAdapter:
    def __init__(
        self, article_map: dict[str, str] | None = None, throttle_s: float = 0.2
    ) -> None:
        self._article_map = article_map or {}
        self._throttle_s = throttle_s

    def _throttle(self) -> None:
        time.sleep(self._throttle_s)

    def get_attention_series(
        self, ticker: str, start: datetime, end: datetime
    ) -> list[AttentionPoint]:
        article = self._article_map.get(ticker, ticker)
        url = _API.format(
            article=article.replace(" ", "_"),
            start=start.strftime("%Y%m%d"),
            end=end.strftime("%Y%m%d"),
        )
        try:
            self._throttle()
            resp = requests.get(url, headers=_HEADERS, timeout=15)
            resp.raise_for_status()
            items = resp.json().get("items", [])
        except Exception as exc:  # noqa: BLE001
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
