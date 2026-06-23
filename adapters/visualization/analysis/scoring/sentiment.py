"""Sentiment scoring for stock analysis."""

from __future__ import annotations

from typing import Any, Literal

from adapters.visualization.analysis.models import SectionScore


def score_sentiment(buzz: list[Any]) -> SectionScore:
    """5 sentiment checks: avg positive, multiple sources, above-average buzz, no negative spike, bullish divergence."""
    verdicts: list[tuple[Literal["pass", "warn", "fail"], str]] = []
    score = 0

    if not buzz:
        return SectionScore(
            "Sentiment",
            0,
            5,
            "No sentiment signals collected yet for this ticker.",
            [("warn", "No buzz signals in database — run daily scan to populate")],
        )

    # Compute stats
    sentiments = [float(b.sentiment_raw) for b in buzz if hasattr(b, "sentiment_raw")]
    sources = set(getattr(b, "source", "unknown") for b in buzz)

    # 1. Avg sentiment > 0
    if sentiments:
        avg_sent = sum(sentiments) / len(sentiments)
        if avg_sent > 0:
            score += 1
            verdicts.append(("pass", f"Average sentiment is positive ({avg_sent:.2f})"))
        else:
            verdicts.append(("fail", f"Average sentiment is negative ({avg_sent:.2f})"))
    else:
        verdicts.append(("warn", "Sentiment scores not available"))

    # 2. Multiple sources agree
    if len(sources) >= 2:
        score += 1
        verdicts.append(
            ("pass", f"{len(sources)} sources active: {', '.join(sorted(sources))}")
        )
    else:
        verdicts.append(
            ("warn", f"Only {len(sources)} source active — limited signal diversity")
        )

    # 3. Buzz above average (mention count heuristic)
    mention_counts = [getattr(b, "mention_count", 0) for b in buzz]
    if mention_counts:
        avg_mentions = sum(mention_counts) / len(mention_counts)
        if avg_mentions >= 3:
            score += 1
            verdicts.append(
                (
                    "pass",
                    f"Average buzz volume {avg_mentions:.1f} mentions/signal — above average",
                )
            )
        else:
            verdicts.append(
                ("warn", f"Low buzz volume ({avg_mentions:.1f} mentions/signal)")
            )
    else:
        verdicts.append(("warn", "Mention count data not available"))

    # 4. No negative sentiment spike (no single signal < -0.5)
    if sentiments:
        min_sent = min(sentiments)
        if min_sent >= -0.5:
            score += 1
            verdicts.append(
                ("pass", "No major negative sentiment spike detected in recent signals")
            )
        else:
            verdicts.append(
                ("fail", f"Negative sentiment spike detected (min: {min_sent:.2f})")
            )
    else:
        verdicts.append(("warn", "Cannot check for spikes — no sentiment data"))

    # 5. Bullish divergence: most recent signals are positive
    recent = buzz[:5] if len(buzz) >= 5 else buzz
    recent_sentiments = [float(getattr(b, "sentiment_raw", 0)) for b in recent]
    if recent_sentiments:
        recent_avg = sum(recent_sentiments) / len(recent_sentiments)
        if recent_avg > 0:
            score += 1
            verdicts.append(
                ("pass", f"Most recent signals are bullish (avg {recent_avg:.2f})")
            )
        else:
            verdicts.append(
                ("warn", f"Recent signals lean bearish (avg {recent_avg:.2f})")
            )
    else:
        verdicts.append(("warn", "Cannot evaluate recent signal trend"))

    pct_score = score / 5
    if pct_score >= 0.60:
        summary = (
            "Sentiment signals are predominantly positive across multiple sources."
        )
    elif pct_score >= 0.40:
        summary = "Mixed sentiment — positive bias with some noise signals."
    else:
        summary = "Sentiment is weak or bearish — caution warranted."

    return SectionScore("Sentiment", score, 5, summary, verdicts)
