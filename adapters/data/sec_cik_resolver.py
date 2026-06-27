"""Ticker → SEC CIK resolver.

The SEC filing adapters (``sec_filing_text_adapter``) need a company's numeric CIK to hit the
submissions API, but callers only have tickers. The SEC publishes the full mapping as a single
public JSON file (``company_tickers.json``), so this adapter fetches it once, caches it (in
memory, and optionally on disk so the one-time Lazy Prices fetch survives process restarts), and
answers ``resolve(ticker) -> int | None``.

Point-in-time note: this is a *current* ticker→CIK map (CIKs are stable identifiers; a company
keeps its CIK across ticker changes). It is used only to LOCATE a company's filings, never as a
predictive feature, so it carries no look-ahead risk.
"""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

import requests
from loguru import logger

_COMPANY_TICKERS_URL = "https://www.sec.gov/files/company_tickers.json"


class SECCikResolver:
    """Resolve a ticker to its SEC CIK via the public company_tickers.json map."""

    def __init__(
        self,
        rate_limit_seconds: float = 1.0,
        user_agent: str = "StockRecommender research@example.com",
        cache_path: Path | None = None,
    ) -> None:
        self._rate_limit_seconds = rate_limit_seconds
        self._last_request_time = 0.0
        self._user_agent = user_agent
        self._cache_path = cache_path
        self._map: dict[str, int] | None = None  # lazily built ticker -> cik

    def _throttle(self) -> None:
        elapsed = time.time() - self._last_request_time
        if elapsed < self._rate_limit_seconds:
            time.sleep(self._rate_limit_seconds - elapsed)
        self._last_request_time = time.time()

    def _fetch_raw(self) -> Any | None:
        headers = {"User-Agent": self._user_agent}
        try:
            self._throttle()
            resp = requests.get(_COMPANY_TICKERS_URL, headers=headers, timeout=20)
            resp.raise_for_status()
            return resp.json()
        except Exception as exc:  # noqa: BLE001 — adapters fail soft
            logger.warning("SEC company_tickers fetch failed: {}", exc)
            return None

    @staticmethod
    def _build_map(raw: Any) -> dict[str, int]:
        """Turn the SEC payload ({"0": {"cik_str", "ticker", ...}, ...}) into ticker->cik.

        Tickers are upper-cased. SEC uses '-' for class shares (e.g. BRK-B); we also index a
        '.'-normalised alias (BRK.B) so callers using either convention resolve.
        """
        out: dict[str, int] = {}
        rows = raw.values() if isinstance(raw, dict) else raw
        for row in rows:
            try:
                ticker = str(row["ticker"]).upper().strip()
                cik = int(row["cik_str"])
            except (KeyError, ValueError, TypeError):
                continue
            if not ticker:
                continue
            out[ticker] = cik
            if "-" in ticker:
                out.setdefault(ticker.replace("-", "."), cik)
        return out

    def _ensure_map(self) -> dict[str, int]:
        if self._map is not None:
            return self._map
        # Disk cache first (so a prior fetch persists across runs).
        if self._cache_path is not None and self._cache_path.exists():
            try:
                raw = json.loads(self._cache_path.read_text())
                self._map = self._build_map(raw)
                return self._map
            except (ValueError, OSError) as exc:
                logger.warning("CIK cache read failed ({}); refetching", exc)
        raw = self._fetch_raw()
        if raw is None:
            self._map = {}
            return self._map
        if self._cache_path is not None:
            try:
                self._cache_path.parent.mkdir(parents=True, exist_ok=True)
                self._cache_path.write_text(json.dumps(raw))
            except OSError as exc:
                logger.warning("CIK cache write failed: {}", exc)
        self._map = self._build_map(raw)
        return self._map

    def resolve(self, ticker: str) -> int | None:
        """Return the CIK for *ticker*, or None if unknown. Case-insensitive."""
        return self._ensure_map().get(ticker.upper().strip())
