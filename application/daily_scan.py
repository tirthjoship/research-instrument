"""Daily buzz discovery scan (ADR-022).

Scans RSS feeds, extracts ticker mentions, scores with keyword + Flan-T5
in parallel (ADR-008). Stores scored signals in buzz_signals table.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Callable, Protocol

from loguru import logger

from domain.models import BuzzSignal


class BuzzScanner(Protocol):
    """Port: discovers raw buzz signals from external sources."""

    def scan_sources(self, scan_time: datetime) -> list[BuzzSignal]: ...


class TextScorer(Protocol):
    """Port: scores text for sentiment, returning domain Sentiment objects."""

    def score_text(
        self, ticker: str, text: str, timestamp: datetime, source: str
    ) -> list[Any]: ...


class DailyScanUseCase:
    """Orchestrates daily buzz discovery and dual-scorer sentiment tagging.

    Injects dependencies via constructor (hexagonal pattern).  No concrete
    adapter types are referenced — only the Protocol interfaces above.
    """

    def __init__(
        self,
        discovery: BuzzScanner,
        keyword_scorer: TextScorer,
        flan_t5_scorer: TextScorer,
        store_signal: Callable[[BuzzSignal], None],
    ) -> None:
        self._discovery = discovery
        self._keyword = keyword_scorer
        self._flan_t5 = flan_t5_scorer
        self._store = store_signal

    def execute(self, scan_time: datetime) -> dict[str, int]:
        """Run a full daily scan cycle.

        Returns:
            dict with keys ``tickers_found`` and ``signals_stored``.
        """
        # 1. Discover raw buzz signals
        raw_signals = self._discovery.scan_sources(scan_time)
        logger.info("Discovered {} raw buzz signal(s)", len(raw_signals))

        if not raw_signals:
            return {"tickers_found": 0, "signals_stored": 0}

        # 2. Persist raw signals immediately (before scoring)
        for signal in raw_signals:
            self._store(signal)

        # 3. Group article hashes + metadata by ticker for scoring
        ticker_texts: dict[str, list[tuple[str, datetime, str]]] = {}
        for s in raw_signals:
            ticker_texts.setdefault(s.ticker, []).append(
                (s.article_hash, s.fetched_at, s.source)
            )

        # 4. Score each (ticker, text) pair with keyword scorer then Flan-T5
        scored_count = 0
        for ticker, texts in ticker_texts.items():
            for text, ts, source in texts:
                # Keyword scorer
                kw_results = self._keyword.score_text(ticker, text, ts, source)
                for sent in kw_results:
                    self._store(
                        BuzzSignal(
                            ticker=ticker,
                            source=source,
                            mention_count=1,
                            sentiment_raw=sent.sentiment_score,
                            scorer="keyword",
                            fetched_at=ts,
                            article_hash=f"kw_{ticker}_{ts.isoformat()}",
                        )
                    )
                    scored_count += 1

                # Flan-T5 scorer
                ft_results = self._flan_t5.score_text(ticker, text, ts, source)
                for sent in ft_results:
                    self._store(
                        BuzzSignal(
                            ticker=ticker,
                            source=source,
                            mention_count=1,
                            sentiment_raw=sent.sentiment_score,
                            scorer="flan_t5",
                            fetched_at=ts,
                            article_hash=f"ft_{ticker}_{ts.isoformat()}",
                        )
                    )
                    scored_count += 1

        logger.info(
            "Scoring complete — tickers={}, scored_signals={}",
            len(ticker_texts),
            scored_count,
        )
        return {"tickers_found": len(ticker_texts), "signals_stored": scored_count}
