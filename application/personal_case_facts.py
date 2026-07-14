"""Real-signal helpers for Home + Portfolio's cited-case feature, shared by
the live get_case_on_expand() path (weekly_brief.py, portfolio_detail.py)
and the weekly-brief CLI's --cite-cases prefetch (brief_commands.py), so a
cache hit and a live fallback never disagree on the facts a case was built
from.

Honesty rule: no real signal -> omit, never fabricate.
"""

from __future__ import annotations

from adapters.visualization.price_cache import _fetch_recent_news_impl
from application.news_context import NewsItem
from application.screener_sentiment_facts import buzz_sentiment_fact


def personal_case_news(ticker: str) -> list[NewsItem]:
    """Real recent headlines for *ticker*, converted to NewsItem. [] on fetch failure."""
    raw = _fetch_recent_news_impl(ticker)
    return [NewsItem(**item) for item in raw]


def personal_case_extra_facts(
    ticker: str,
    *,
    verdict: str,
    why: str,
    db_path: str = "data/recommendations.db",
) -> tuple[str, ...]:
    """Verdict/why fact plus a real buzz-sentiment fact when one exists.

    The buzz fact is omitted (not fabricated) on no signals — mirrors
    application.screener_sentiment_facts.buzz_sentiment_fact's own honesty rule.
    """
    facts = [f"Verdict: {verdict}. {why}"]
    buzz = buzz_sentiment_fact(ticker, db_path)
    if buzz is not None:
        facts.append(buzz)
    return tuple(facts)
