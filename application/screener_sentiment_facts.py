"""Real market-sentiment fact for a Screener candidate, sourced from the
existing BuzzSignal store (same infra Stock Analysis's buzz view already
reads). Honesty rule: no signals -> None (an honest omission), never a
fabricated "no buzz" claim baked into the fact text.
"""

from __future__ import annotations

from adapters.visualization.analysis.loaders import load_buzz_signals

_STRONGLY_POSITIVE = 0.5
_MILDLY_POSITIVE = 0.15
_MILDLY_NEGATIVE = -0.15
_STRONGLY_NEGATIVE = -0.5


def sentiment_label(mean_sentiment: float) -> str:
    """Bucket a mean BuzzSignal.sentiment_raw ([-1, 1]) into plain-English text.

    Public and shared: Stock Analysis's ai_read.py reuses this on
    result.buzz_signals (already fetched by analyze_ticker(), no second DB
    query) instead of duplicating the threshold logic.
    """
    if mean_sentiment >= _STRONGLY_POSITIVE:
        return "strongly positive"
    if mean_sentiment >= _MILDLY_POSITIVE:
        return "mildly positive"
    if mean_sentiment > _MILDLY_NEGATIVE:
        return "neutral"
    if mean_sentiment > _STRONGLY_NEGATIVE:
        return "mildly negative"
    return "strongly negative"


def buzz_sentiment_fact(
    ticker: str, db_path: str = "data/recommendations.db"
) -> str | None:
    """Return a real-signal market-sentiment fact string, or None on no data.

    Aggregates BuzzSignal.sentiment_raw (mean, [-1, 1] scale) across the
    signals load_buzz_signals() returns for *ticker*, and formats e.g.
    "Recent buzz: mildly positive sentiment (0.30), 12 mentions in the last
    30d". Returns None when there are no signals — never fabricates a
    "no buzz" claim.
    """
    signals, _stale = load_buzz_signals(ticker, db_path)
    if not signals:
        return None
    total_mentions = sum(int(getattr(s, "mention_count", 0)) for s in signals)
    mean_sentiment = sum(
        float(getattr(s, "sentiment_raw", 0.0)) for s in signals
    ) / len(signals)
    label = sentiment_label(mean_sentiment)
    return (
        f"Recent buzz: {label} sentiment ({mean_sentiment:.2f}), "
        f"{total_mentions} mentions in the last 30d"
    )
