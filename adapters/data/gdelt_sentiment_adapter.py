"""GDELT sentiment adapter — HistoricalSentimentPort via GDELT DOC API."""

from __future__ import annotations

import hashlib
import io
import time
from datetime import datetime, timezone

import requests
from loguru import logger

from domain.models import BuzzSignal, Sentiment

_GDELT_DOC_API = "https://api.gdeltproject.org/api/v2/doc/doc"
_GDELT_CONFIDENCE = 0.6


class GdeltSentimentAdapter:
    """HistoricalSentimentPort implementation using the GDELT DOC API.

    Queries GDELT for news articles mentioning a symbol and converts the
    V2Tone field into normalised [-1, 1] sentiment scores for backtesting.
    """

    def __init__(
        self,
        rate_limit_seconds: float = 1.0,
        *,
        throttle_s: float | None = None,
        max_retries: int = 3,
    ) -> None:
        # throttle_s is the new keyword alias; rate_limit_seconds preserved for compat
        if throttle_s is not None:
            self._rate_limit_seconds = throttle_s
        else:
            self._rate_limit_seconds = rate_limit_seconds
        self._max_retries = max_retries
        self._last_request_time: float = 0.0

    @property
    def rate_limit_seconds(self) -> float:
        return self._rate_limit_seconds

    def _throttle(self) -> None:
        elapsed = time.time() - self._last_request_time
        if elapsed < self._rate_limit_seconds:
            time.sleep(self._rate_limit_seconds - elapsed)
        self._last_request_time = time.time()

    def _get_with_retry(self, params: dict[str, str], symbol: str) -> str:
        """Execute a GDELT DOC API request with exponential backoff on 429.

        Returns the response text on success, or "" on permanent failure.
        """
        for attempt in range(self._max_retries):
            try:
                self._throttle()
                response = requests.get(_GDELT_DOC_API, params=params, timeout=15)
                response.raise_for_status()
                text = response.text
                if text.count("\n") >= 250:  # header + 250 data rows
                    logger.warning(
                        "GDELT maxrecords hit for {} — results truncated", symbol
                    )
                return text
            except requests.HTTPError as exc:
                status = exc.response.status_code if exc.response is not None else 0
                if status == 429 and attempt < self._max_retries - 1:
                    wait = 2**attempt
                    logger.warning(
                        "GDELT 429 for {} (attempt {}/{}), retrying in {}s",
                        symbol,
                        attempt + 1,
                        self._max_retries,
                        wait,
                    )
                    time.sleep(wait)
                    continue
                logger.warning("GDELT HTTP {} for symbol {}: {}", status, symbol, exc)
                return ""
            except Exception as exc:  # noqa: BLE001
                logger.warning("GDELT request failed for symbol {}: {}", symbol, exc)
                return ""
        return ""

    def get_historical_sentiment(
        self,
        symbol: str,
        start_date: datetime,
        end_date: datetime,
    ) -> list[Sentiment]:
        """Return GDELT-derived Sentiment objects for symbol in [start_date, end_date].

        Queries GDELT DOC API, parses tab-separated ArtList response,
        and converts V2Tone to normalised sentiment scores.

        Returns an empty list on any network or parse error.
        """
        params: dict[str, str] = {
            "query": f'"{symbol}" sourcelang:eng',
            "mode": "ArtList",
            "format": "csv",
            "startdatetime": start_date.strftime("%Y%m%d%H%M%S"),
            "enddatetime": end_date.strftime("%Y%m%d%H%M%S"),
            "maxrecords": "250",
        }
        text = self._get_with_retry(params, symbol)
        if not text:
            return []
        return self._parse_csv_response(text, symbol)

    def get_historical_buzz(
        self,
        ticker: str,
        start_date: datetime,
        end_date: datetime,
    ) -> list[BuzzSignal]:
        """Return BuzzSignal objects derived from GDELT article mentions.

        Each article row in the ArtList response becomes one BuzzSignal with
        fetched_at = the real article publication date (not now()).
        """
        params: dict[str, str] = {
            "query": f'"{ticker}" sourcelang:eng',
            "mode": "ArtList",
            "format": "csv",
            "startdatetime": start_date.strftime("%Y%m%d%H%M%S"),
            "enddatetime": end_date.strftime("%Y%m%d%H%M%S"),
            "maxrecords": "250",
        }
        text = self._get_with_retry(params, ticker)
        if not text:
            return []

        results: list[BuzzSignal] = []
        lines = text.strip().splitlines()
        for i, line in enumerate(lines):
            if i == 0:
                continue  # skip header
            if not line:
                continue
            cols = line.split("\t")
            if not cols[0]:
                continue
            try:
                ts = datetime.strptime(cols[0], "%Y%m%d%H%M%S").replace(
                    tzinfo=timezone.utc
                )
            except ValueError:
                continue
            article_hash = hashlib.sha256(
                f"gdelt:{ticker}:{cols[0]}:{i}".encode()
            ).hexdigest()
            results.append(
                BuzzSignal(
                    ticker=ticker,
                    source="gdelt",
                    mention_count=1,
                    sentiment_raw=0.0,
                    scorer="gdelt",
                    fetched_at=ts,
                    article_hash=article_hash,
                )
            )
        return results

    def _parse_csv_response(self, csv_text: str, symbol: str) -> list[Sentiment]:
        """Parse GDELT tab-separated ArtList CSV into Sentiment objects.

        Expected columns (0-indexed):
          0 — DATE (YYYYMMDDHHMMSS)
          1 — SourceCommonName
          2 — DocumentIdentifier (URL)
          ...
          V2Tone — located by header name; format: "tone,pos,neg,polarity,..."
        """
        results: list[Sentiment] = []
        reader = io.StringIO(csv_text.strip())
        lines = reader.readlines()

        if not lines:
            return []

        header_line = lines[0].rstrip("\n")
        headers = [h.strip() for h in header_line.split("\t")]

        # Locate required column indices by header name
        try:
            v2tone_idx = headers.index("V2Tone")
            date_idx = headers.index("DATE")
            source_idx = headers.index("SourceCommonName")
        except ValueError:
            # Fall back to positional indices when headers are absent / numeric
            # GDELT ArtList positional layout:
            #   0=DATE, 1=SourceCommonName, 2=DocumentIdentifier, 3=... 17=V2Tone
            date_idx = 0
            source_idx = 1
            v2tone_idx = 17
            # Re-include header line as a data row if it looks like a date
            lines = lines  # already includes first line; will be filtered below

        data_lines = (
            lines[1:]
            if header_line.startswith("DATE") or header_line.startswith("date")
            else lines
        )

        for line in data_lines:
            line = line.rstrip("\n")
            if not line:
                continue
            cols = line.split("\t")
            if len(cols) <= max(date_idx, source_idx, v2tone_idx):
                continue
            try:
                raw_date = cols[date_idx].strip()
                source_name = cols[source_idx].strip() or "unknown"
                v2tone_raw = cols[v2tone_idx].strip()

                # V2Tone: "tone,positive,negative,polarity,..." — first value is tone
                tone_str = v2tone_raw.split(",")[0]
                tone = float(tone_str)

                # Normalise: GDELT tone ~ [-10, +10] → [-1, 1]
                score = max(-1.0, min(1.0, tone / 10.0))

                # Parse GDELT date: YYYYMMDDHHMMSS
                ts = datetime.strptime(raw_date, "%Y%m%d%H%M%S").replace(
                    tzinfo=timezone.utc
                )

                results.append(
                    Sentiment(
                        source=f"gdelt_{source_name}",
                        timestamp=ts,
                        sentiment_score=score,
                        confidence=_GDELT_CONFIDENCE,
                        text_snippet=None,
                    )
                )
            except (ValueError, IndexError) as exc:
                logger.warning("GDELT: skipping malformed row for {}: {}", symbol, exc)
                continue

        return results
