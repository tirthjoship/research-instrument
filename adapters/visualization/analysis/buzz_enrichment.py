"""Live headline scoring when harvested buzz has no directional tone."""

from __future__ import annotations

from datetime import datetime, timezone
from types import SimpleNamespace
from typing import Any

_SCORED_SCORERS = frozenset({"keyword", "keyword_live", "flan_t5"})

# Chip-sector / market headline terms beyond the generic keyword list.
_EXTRA_BULLISH = (
    "beat",
    "surge",
    "rally",
    "soar",
    "upgrade",
    "outperform",
    "record high",
    "all-time high",
)
_EXTRA_BEARISH = (
    "dip",
    "dips",
    "drop",
    "drops",
    "crash",
    "crashed",
    "plunge",
    "plummet",
    "plummeting",
    "selloff",
    "sell-off",
    "miss",
    "downgrade",
    "warning",
    "worries",
    "fear",
)


def _parse_headline_date(raw: str) -> datetime:
    s = (raw or "").strip()[:10]
    if not s:
        return datetime.now(timezone.utc)
    try:
        return datetime.strptime(s, "%Y-%m-%d").replace(tzinfo=timezone.utc)
    except ValueError:
        return datetime.now(timezone.utc)


def _headline_sentiment_score(
    kw: Any,
    ticker: str,
    title: str,
    fetched: datetime,
    publisher: str,
) -> float:
    """Keyword score blended with finance-headline term hits on title only."""
    base = float(kw.score_text(ticker, title, fetched, publisher)[0].sentiment_score)
    low = title.lower()
    bull = sum(1 for term in _EXTRA_BULLISH if term in low)
    bear = sum(1 for term in _EXTRA_BEARISH if term in low)
    if bull + bear == 0:
        return base
    extra = (bull - bear) / (bull + bear)
    blended = 0.55 * base + 0.45 * extra
    return max(-1.0, min(1.0, blended))


def _publisher_from_headline(h: dict[str, Any]) -> str:
    pub = str(h.get("source", "") or "").strip()
    return pub or "News"


def score_headlines_as_buzz_signals(
    ticker: str,
    headlines: list[dict[str, Any]],
) -> list[Any]:
    """Keyword-score yfinance headlines into ephemeral buzz rows.

    Each row uses the attributed publisher as ``source`` / ``publisher`` so
    sentiment panels can show Reuters vs Motley Fool, not one blob.
    """
    if not headlines:
        return []
    from adapters.ml.keyword_scorer import KeywordScorer

    kw = KeywordScorer()
    out: list[Any] = []
    for i, h in enumerate(headlines):
        title = str(h.get("title", "") or "")
        publisher = _publisher_from_headline(h)
        if not title.strip():
            continue
        fetched = _parse_headline_date(str(h.get("date", "") or ""))
        score = _headline_sentiment_score(kw, ticker, title, fetched, publisher)
        out.append(
            SimpleNamespace(
                ticker=ticker,
                source=publisher,
                publisher=publisher,
                mention_count=1,
                sentiment_raw=score,
                scorer="keyword_live",
                fetched_at=fetched,
                article_hash=f"live_{ticker}_{i}_{fetched.date().isoformat()}",
                article_text=title[:2000],
            )
        )
    return out


def _distinct_days(signals: list[Any]) -> int:
    dates = {str(getattr(s, "fetched_at", "") or "")[:10] for s in signals}
    dates.discard("")
    return len(dates)


def resolve_sentiment_signals(
    harvest: list[Any],
    harvest_stale: bool,
    ticker: str,
    headlines: list[dict[str, Any]] | None,
) -> tuple[list[Any], bool, bool]:
    """Pick signals for the Sentiment panel only (harvest buzz stays separate).

    Prefers live yfinance headlines when harvest is tone-flat, single-day sparse,
    or thinner than the live headline set — even if a few harvest rows scored nonzero.

    Returns:
        (sentiment_signals, from_live, sentiment_stale)
    """
    if not headlines:
        return harvest, False, harvest_stale

    live = score_headlines_as_buzz_signals(ticker, headlines)
    if not live:
        return harvest, False, harvest_stale

    has_tone = any(
        abs(float(getattr(b, "sentiment_raw", 0) or 0)) > 0.05
        for b in harvest
        if getattr(b, "scorer", None) in _SCORED_SCORERS
    )

    if has_tone:
        return harvest, False, harvest_stale

    return live, True, False


def apply_live_buzz_fallback(
    buzz: list[Any],
    stale: bool,
    ticker: str,
    headlines: list[dict[str, Any]] | None,
) -> tuple[list[Any], bool]:
    """Deprecated: mutates buzz+sentiment together. Prefer ``resolve_sentiment_signals``."""
    signals, _, sentiment_stale = resolve_sentiment_signals(
        buzz, stale, ticker, headlines
    )
    return signals, sentiment_stale
