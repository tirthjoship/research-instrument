"""SEC EDGAR adapter — SmartMoneyPort via EFTS full-text search API."""

from __future__ import annotations

import time
from typing import Any

import requests
from loguru import logger

from domain.conviction import SmartMoneySignal, SmartMoneyType

_EFTS_API = "https://efts.sec.gov/LATEST/search-index"

# SC 13D filers are activist investors by definition (>5% with intent to influence)
_ACTIVIST_FORMS = {"SC 13D", "SC 13D/A"}


class SECEdgarAdapter:
    """SmartMoneyPort implementation using the SEC EDGAR EFTS full-text search API.

    Queries EDGAR for SC 13D activist filings and Form 4 insider transactions,
    converting raw EFTS JSON hits into SmartMoneySignal domain objects.
    """

    def __init__(
        self,
        rate_limit_seconds: float = 1.0,
        user_agent: str = "StockRecommender research@example.com",
    ) -> None:
        self._rate_limit_seconds = rate_limit_seconds
        self._last_request_time: float = 0.0
        self._user_agent = user_agent

    @property
    def rate_limit_seconds(self) -> float:
        return self._rate_limit_seconds

    def _throttle(self) -> None:
        elapsed = time.time() - self._last_request_time
        if elapsed < self._rate_limit_seconds:
            time.sleep(self._rate_limit_seconds - elapsed)
        self._last_request_time = time.time()

    def _fetch(self, params: dict[str, str]) -> list[dict[str, Any]]:
        """Fetch hits from EFTS API, returning raw _source dicts.

        Returns an empty list on any HTTP or parse error.
        """
        headers = {"User-Agent": self._user_agent}
        try:
            self._throttle()
            response = requests.get(
                _EFTS_API, params=params, headers=headers, timeout=15
            )
            response.raise_for_status()
            data: dict[str, Any] = response.json()
            hits: list[dict[str, Any]] = data.get("hits", {}).get("hits", [])
            return hits
        except requests.HTTPError as exc:
            status = exc.response.status_code if exc.response is not None else "?"
            logger.warning(
                "SEC EDGAR HTTP {} for query {}: {}", status, params.get("q"), exc
            )
            return []
        except Exception as exc:  # noqa: BLE001
            logger.warning(
                "SEC EDGAR request failed for query {}: {}", params.get("q"), exc
            )
            return []

    def _parse_hit(
        self, hit: dict[str, Any], signal_type: SmartMoneyType
    ) -> SmartMoneySignal | None:
        """Convert a single EFTS hit into a SmartMoneySignal.

        Returns None if required fields are missing.
        """
        try:
            src = hit["_source"]
            display_names: list[str] = src.get("display_names") or []
            filer_name = display_names[0] if display_names else "Unknown"
            form_type: str = src.get("form_type", "")
            is_activist = form_type.strip() in _ACTIVIST_FORMS

            return SmartMoneySignal(
                ticker=src.get("ticker", "").upper(),
                signal_type=signal_type,
                filer_name=filer_name,
                stake_pct=None,
                transaction_value=0.0,
                filed_date=src.get("file_date", ""),
                is_activist=is_activist,
                source_url=f"https://www.sec.gov/cgi-bin/browse-edgar?action=getcompany&filenum={src.get('file_num', '')}&type={form_type}&dateb=&owner=include&count=40",
            )
        except (KeyError, IndexError, TypeError) as exc:
            logger.warning(
                "SEC EDGAR: skipping malformed hit {}: {}", hit.get("_id"), exc
            )
            return None

    def get_13d_filings(self, ticker: str, since_date: str) -> list[SmartMoneySignal]:
        """Return SC 13D activist filings for *ticker* since *since_date* (YYYY-MM-DD).

        Returns an empty list on any network or parse error.
        """
        params = {
            "q": ticker,
            "forms": "SC 13D",
            "startdt": since_date,
        }
        hits = self._fetch(params)
        signals: list[SmartMoneySignal] = []
        for hit in hits:
            sig = self._parse_hit(hit, SmartMoneyType.FORM_13D)
            if sig is not None:
                signals.append(sig)
        logger.info(
            "SEC EDGAR 13D: {} signals for {} since {}",
            len(signals),
            ticker,
            since_date,
        )
        return signals

    def get_form4_filings(self, ticker: str, since_date: str) -> list[SmartMoneySignal]:
        """Return Form 4 insider transaction filings for *ticker* since *since_date*.

        Returns an empty list on any network or parse error.
        """
        params = {
            "q": ticker,
            "forms": "4",
            "startdt": since_date,
        }
        hits = self._fetch(params)
        signals: list[SmartMoneySignal] = []
        for hit in hits:
            sig = self._parse_hit(hit, SmartMoneyType.FORM_4)
            if sig is not None:
                signals.append(sig)
        logger.info(
            "SEC EDGAR Form4: {} signals for {} since {}",
            len(signals),
            ticker,
            since_date,
        )
        return signals

    def get_all_signals(self, ticker: str, since_date: str) -> list[SmartMoneySignal]:
        """Return combined 13D + Form 4 signals for *ticker* since *since_date*.

        Convenience method that calls both underlying methods and concatenates results.
        """
        return self.get_13d_filings(ticker, since_date) + self.get_form4_filings(
            ticker, since_date
        )
