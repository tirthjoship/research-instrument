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

        # 3. Score each article's headline+summary text (not the dedup hash)
        scored_count = 0
        tickers_seen: set[str] = set()
        for s in raw_signals:
            text = (s.article_text or "").strip()
            if not text:
                logger.debug(
                    "Skipping score for {} — no article_text on {}",
                    s.ticker,
                    s.article_hash,
                )
                continue
            tickers_seen.add(s.ticker)
            for scorer_name, scorer, prefix in (
                ("keyword", self._keyword, "kw"),
                ("flan_t5", self._flan_t5, "ft"),
            ):
                results = scorer.score_text(s.ticker, text, s.fetched_at, s.source)
                for sent in results:
                    self._store(
                        BuzzSignal(
                            ticker=s.ticker,
                            source=s.source,
                            mention_count=s.mention_count,
                            sentiment_raw=sent.sentiment_score,
                            scorer=scorer_name,
                            fetched_at=s.fetched_at,
                            article_hash=f"{prefix}_{s.article_hash}",
                            article_text=text[:2000],
                        )
                    )
                    scored_count += 1

        logger.info(
            "Scoring complete — tickers={}, scored_signals={}",
            len(tickers_seen),
            scored_count,
        )
        return {"tickers_found": len(tickers_seen), "signals_stored": scored_count}
