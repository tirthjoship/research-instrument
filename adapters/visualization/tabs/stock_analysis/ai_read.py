"""Stock Analysis Google-AI read — same in-favor/to-watch shape as Home/Portfolio
(render_gemini_read, CaseResult, GeminiNarratorAdapter — no new prompt variant),
fed this tab's own real facts + real news + real buzz sentiment. Cached same-day
per ticker at CACHE_PATH, separate from Home/Portfolio/Risk's weekly cache file
— that file's single as_of field represents one weekly batch prefetch, while this
tab needs entries added incrementally throughout each day as different tickers
are viewed.
"""

from __future__ import annotations

import json
import os
from datetime import date
from pathlib import Path
from typing import Any

from adapters.visualization.components.gemini_read import (
    build_case_context,
    render_gemini_read,
)
from adapters.visualization.price_cache import _fetch_recent_news_impl
from application.card_loading import select_case_summarizer
from application.case_cache import load_cached_case, write_case_cache
from application.runtime_guard import is_local_runtime
from application.screener_sentiment_facts import sentiment_label
from domain.case_models import CaseResult

CACHE_PATH = "data/reports/stock_analysis_cited_cases.json"


def buzz_fact_from_signals(buzz_signals: list[Any]) -> str | None:
    """Real market-sentiment fact from result.buzz_signals (already fetched by
    analyze_ticker() — no second DB query). None on no signals (honest omission,
    mirrors application.screener_sentiment_facts.buzz_sentiment_fact).
    """
    if not buzz_signals:
        return None
    total_mentions = sum(int(getattr(s, "mention_count", 0)) for s in buzz_signals)
    mean_sentiment = sum(
        float(getattr(s, "sentiment_raw", 0.0)) for s in buzz_signals
    ) / len(buzz_signals)
    label = sentiment_label(mean_sentiment)
    return f"Recent buzz: {label} sentiment ({mean_sentiment:.2f}), {total_mentions} mentions"


def get_or_fetch_google_ai_read(ticker: str, facts: dict[str, str]) -> str:
    """Return the rendered .gai HTML block for *ticker*, or "" off-local.

    Cache-first, same-day: a hit at CACHE_PATH for today's date returns instantly,
    zero network calls. On a miss, fetches real news + calls the shared summarizer,
    then read-merge-writes the result into today's cache file (write_case_cache
    overwrites the whole file, so existing same-day entries must be preserved).
    """
    if not is_local_runtime():
        return ""

    today = date.today().isoformat()
    cached = _read_same_day_case(ticker, today)
    if cached is not None:
        return render_gemini_read(cached)

    news_items = _fetch_recent_news_impl(ticker, limit=5)
    ctx = build_case_context(ticker=ticker, facts=facts, news=news_items)
    summarizer = select_case_summarizer()
    result: CaseResult = summarizer.summarize_case(ctx)  # type: ignore[attr-defined]

    if not result.data_gap:
        _write_same_day_case(ticker, today, result)
    return render_gemini_read(result)


def _read_same_day_case(ticker: str, today: str) -> CaseResult | None:
    if not os.path.exists(CACHE_PATH):
        return None
    try:
        payload = json.loads(Path(CACHE_PATH).read_text())
        if payload.get("as_of") != today:
            return None
    except Exception:  # noqa: BLE001
        return None
    return load_cached_case(CACHE_PATH, ticker)


def _write_same_day_case(ticker: str, today: str, result: CaseResult) -> None:
    cases: dict[str, CaseResult] = {}
    if os.path.exists(CACHE_PATH):
        try:
            payload = json.loads(Path(CACHE_PATH).read_text())
            if payload.get("as_of") == today:
                for existing_ticker in payload.get("cases", {}):
                    existing = load_cached_case(CACHE_PATH, existing_ticker)
                    if existing is not None:
                        cases[existing_ticker] = existing
        except Exception:  # noqa: BLE001
            pass  # corrupt/unreadable cache -> start today's file fresh
    cases[ticker] = result
    write_case_cache(CACHE_PATH, today, cases)
