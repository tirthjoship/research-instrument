"""Attributed news/event context aggregation for the Research Instrument.

This module surfaces third-party news items as attributed context
(grouped by source) — it is NOT a forecast. Headlines are labelled
"context, not signal" in every output structure, per ADR-056.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class NewsItem:
    """A single attributed news headline from one named source."""

    source: str
    title: str
    date: str


@dataclass(frozen=True)
class NewsContext:
    """An attributed collection of news items for a ticker research session.

    Attributes:
        items:    Headlines sorted most-recent-first, capped at *limit*.
        label:    Always ``"context, not signal"`` — never a forecast.
        data_gap: True when no headlines were available for the window.
    """

    items: list[NewsItem]
    label: str
    data_gap: bool


def build_news_context(
    signals: list[dict[str, object]],
    limit: int,
) -> NewsContext:
    """Aggregate raw signal dicts into an attributed :class:`NewsContext`.

    Each item in *signals* is expected to have ``"source"``, ``"title"``,
    and ``"date"`` keys.  Missing keys receive safe empty-string defaults.

    Items are sorted by ``date`` descending (most recent first) and
    capped at *limit*.

    The resulting :class:`NewsContext` carries ``label = "context, not signal"``
    and ``data_gap = True`` iff *signals* is empty.

    This function never adopts or re-frames third-party news as a
    forward-looking claim; attribution is by source only (ADR-056).
    """
    items: list[NewsItem] = [
        NewsItem(
            source=str(s.get("source", "")),
            title=str(s.get("title", "")),
            date=str(s.get("date", "")),
        )
        for s in signals
    ]

    items.sort(key=lambda i: i.date, reverse=True)
    items = items[:limit]

    return NewsContext(
        items=items,
        label="context, not signal",
        data_gap=len(signals) == 0,
    )
