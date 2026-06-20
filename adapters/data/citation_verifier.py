"""Verify a citation resolves (HTTP 200) and names the ticker/company.
Unverified claims are dropped (spec §4). Default fetcher is throttled requests."""

from __future__ import annotations

import re
import time
from typing import Callable

# Module-level throttle state for requests_fetcher
_MIN_INTERVAL: float = 0.5  # seconds between outbound requests
_last_request_time: float = 0.0


def requests_fetcher(url: str, timeout: int = 10) -> tuple[int, str]:
    """Fetch *url* with a min-interval throttle. Returns (status_code, text).

    ``requests`` is lazily imported so the module can be loaded without
    the package being present (test environments use injected fakes).
    """
    global _last_request_time  # noqa: PLW0603

    import requests as _requests  # lazy import — not available in all envs

    elapsed = time.time() - _last_request_time
    if elapsed < _MIN_INTERVAL:
        time.sleep(_MIN_INTERVAL - elapsed)
    try:
        resp = _requests.get(url, timeout=timeout)
        _last_request_time = time.time()
        return (resp.status_code, resp.text)
    except Exception:
        _last_request_time = time.time()
        return (0, "")


class CitationVerifier:
    def __init__(
        self,
        fetcher: Callable[[str], tuple[int, str]],
        name_map: dict[str, list[str]],
    ) -> None:
        self._fetch = fetcher
        self._names = name_map

    def verify(self, url: str, ticker: str) -> bool:
        """Return True iff the URL resolves (HTTP 200) and the body mentions the ticker."""
        try:
            status, text = self._fetch(url)
        except Exception:
            return False
        if status != 200 or not text:
            return False
        # Word-boundary match so short tickers (F, A, C) don't false-verify on
        # any page containing that letter — the anti-hallucination gate (spec §4).
        needles = [ticker] + self._names.get(ticker, [])
        return any(
            re.search(rf"\b{re.escape(n)}\b", text, re.IGNORECASE) for n in needles
        )
