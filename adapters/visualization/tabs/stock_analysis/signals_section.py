"""Sentiment, Supply Chain sections."""

from __future__ import annotations

import html as _html
from collections import defaultdict
from dataclasses import dataclass
from typing import Any

from adapters.visualization.components.cards import criteria_card, verdict_bullet
from adapters.visualization.components.charts import cluster_bubble
from adapters.visualization.components.evidence_chip import render_evidence_chip_by_key
from adapters.visualization.stock_analyzer import AnalysisResult

# ---------------------------------------------------------------------------
# Section 6: Sentiment — descriptive digest of attributed buzz
# ---------------------------------------------------------------------------

# Sign thresholds for the positive/neutral/negative tally. Deliberately narrow so
# near-zero scores read as "neutral" rather than being forced to a side.
_POS_THRESHOLD = 0.05
_NEG_THRESHOLD = -0.05


@dataclass(frozen=True)
class SentimentDigest:
    """A purely descriptive summary of a ticker's recent buzz signals.

    Aggregates the raw ``BuzzSignal`` rows the analyzer already loads — no new
    adapters, no forecast. Powers the timeline + source breakdown + tally so the
    section reads as a description of attention, not a trade signal.
    """

    total_signals: int
    total_mentions: int
    positive: int
    neutral: int
    negative: int
    mean_sentiment: float
    sources: tuple[str, ...]
    # (source, mention_count, mean_sentiment) — one row per distinct source.
    source_breakdown: tuple[tuple[str, int, float], ...]
    # (date, mean_sentiment) ascending by date — the sentiment timeline.
    timeline: tuple[tuple[str, float], ...]


def _build_sentiment_digest(buzz: list[Any]) -> SentimentDigest | None:
    """Aggregate raw buzz signals into a descriptive digest. Pure — no Streamlit.

    Returns ``None`` when there are no signals so the caller can render an honest
    empty state. Every field is a description of today's buzz; none is predictive.
    """
    if not buzz:
        return None

    total_signals = len(buzz)
    total_mentions = 0
    pos = neu = neg = 0
    sentiment_sum = 0.0

    by_source_sent: dict[str, list[float]] = defaultdict(list)
    by_source_mentions: dict[str, int] = defaultdict(int)
    by_date_sent: dict[str, list[float]] = defaultdict(list)

    for b in buzz:
        sentiment = float(getattr(b, "sentiment_raw", 0.0) or 0.0)
        mentions = int(getattr(b, "mention_count", 0) or 0)
        source = str(getattr(b, "source", "unknown") or "unknown")
        date = str(getattr(b, "fetched_at", ""))[:10]

        total_mentions += mentions
        sentiment_sum += sentiment
        if sentiment > _POS_THRESHOLD:
            pos += 1
        elif sentiment < _NEG_THRESHOLD:
            neg += 1
        else:
            neu += 1

        by_source_sent[source].append(sentiment)
        by_source_mentions[source] += mentions
        if date:
            by_date_sent[date].append(sentiment)

    source_breakdown = tuple(
        (
            src,
            by_source_mentions[src],
            sum(vals) / len(vals) if vals else 0.0,
        )
        for src, vals in sorted(
            by_source_sent.items(),
            key=lambda kv: by_source_mentions[kv[0]],
            reverse=True,
        )
    )
    timeline = tuple(
        (date, sum(vals) / len(vals) if vals else 0.0)
        for date, vals in sorted(by_date_sent.items())
    )

    return SentimentDigest(
        total_signals=total_signals,
        total_mentions=total_mentions,
        positive=pos,
        neutral=neu,
        negative=neg,
        mean_sentiment=sentiment_sum / total_signals if total_signals else 0.0,
        sources=tuple(src for src, _, _ in source_breakdown),
        source_breakdown=source_breakdown,
        timeline=timeline,
    )


def _sentiment_tally_html(digest: SentimentDigest) -> str:
    """Build the positive/neutral/negative tally + source-breakdown card. Pure HTML."""
    chip = render_evidence_chip_by_key("sentiment_signal")
    src_count = len(digest.sources)
    src_word = "source" if src_count == 1 else "sources"

    def _pill(label: str, count: int, colour: str) -> str:
        return (
            f'<span style="display:inline-block;margin-right:14px;font-size:13px;">'
            f'<span style="font-weight:700;color:{colour};">{count}</span> '
            f'<span style="color:#64748B;">{label}</span></span>'
        )

    rows = []
    for src, mentions, mean_s in digest.source_breakdown:
        s_colour = (
            "#16A34A"
            if mean_s > _POS_THRESHOLD
            else "#DC2626" if mean_s < _NEG_THRESHOLD else "#64748B"
        )
        rows.append(
            f'<div style="display:flex;justify-content:space-between;'
            f'padding:3px 0;border-bottom:1px solid #F1F5F9;font-size:12px;">'
            f'<span style="color:#0F6E80;font-weight:500;">{_html.escape(src)}</span>'
            f'<span style="color:#94A3B8;">{mentions} mention(s) · '
            f'avg <span style="color:{s_colour};font-weight:600;">{mean_s:+.2f}</span>'
            f"</span></div>"
        )

    return (
        f'<div class="ws-card" style="padding:12px 16px;margin-bottom:10px;">'
        f'<div style="display:flex;align-items:center;justify-content:space-between;'
        f'margin-bottom:8px;">'
        f'<span style="font-weight:600;font-size:14px;color:#1A202C;">'
        f"Buzz mix · {digest.total_signals} signal(s) across {src_count} {src_word}</span>"
        f"{chip}</div>"
        f'<div style="margin-bottom:8px;">'
        f"{_pill('positive', digest.positive, '#16A34A')}"
        f"{_pill('neutral', digest.neutral, '#64748B')}"
        f"{_pill('negative', digest.negative, '#DC2626')}"
        f'<span style="font-size:12px;color:#94A3B8;">'
        f"mean score {digest.mean_sentiment:+.2f} · {digest.total_mentions} mention(s)</span>"
        f"</div>"
        f"<div>{''.join(rows)}</div>"
        f"</div>"
    )


def _render_sentiment(result: AnalysisResult) -> None:
    import streamlit as st

    st.divider()
    section = result.sentiment
    if not section:
        return
    st.markdown("#### 6. Sentiment")
    st.caption(
        "Descriptive buzz only — predictive value was tested and falsified "
        "(ADR-044: no cross-sectional IC on a clean 430-ticker universe)."
    )
    st.markdown(
        criteria_card(section.title, section.score, section.max_score, section.summary),
        unsafe_allow_html=True,
    )

    buzz = getattr(result, "sentiment_signals", None) or getattr(
        result, "buzz_signals", None
    )
    digest = _build_sentiment_digest(buzz or [])
    if digest is not None:
        # Tally + source breakdown, with the FALSIFIED sentiment chip attached.
        st.markdown(_sentiment_tally_html(digest), unsafe_allow_html=True)

        # Sentiment timeline (date vs mean score) — a description of how attention
        # moved, not a forecast. Only drawn when >=2 dated points exist.
        if len(digest.timeline) >= 2:
            import pandas as pd

            ts = pd.DataFrame(
                {"score": [s for _, s in digest.timeline]},
                index=[d for d, _ in digest.timeline],
            )
            st.markdown(
                '<div style="font-size:12px;color:#64748B;margin:4px 0;">'
                "Sentiment timeline — mean buzz score by date</div>",
                unsafe_allow_html=True,
            )
            st.line_chart(ts, height=180)
    else:
        st.markdown(
            '<div class="ws-card" style="text-align:center;padding:16px;">'
            '<div style="font-size:14px;color:#64748B;">No sentiment signals in database</div>'
            '<div style="font-size:12px;color:#94A3B8;margin-top:4px;">'
            "Run <code>make daily-scan</code> to populate sentiment data"
            "</div></div>",
            unsafe_allow_html=True,
        )

    for status, text in section.verdicts:
        st.markdown(verdict_bullet(status, text), unsafe_allow_html=True)


# ---------------------------------------------------------------------------
# Section 7: Supply Chain
# ---------------------------------------------------------------------------


def _render_supply_chain(result: AnalysisResult) -> None:
    import streamlit as st

    st.divider()
    section = result.supply_chain
    if not section:
        return
    st.markdown("#### 7. Supply Chain")
    st.markdown(
        criteria_card(section.title, section.score, section.max_score, section.summary),
        unsafe_allow_html=True,
    )

    sc_group = result.supply_chain_group
    if sc_group:
        # Build bubble chart data from peers + self
        all_tickers_in_group = sc_group.get("leaders", []) + sc_group.get(
            "followers", []
        )
        # Use peer_data for market caps; fill in self
        peer_lookup = {p["ticker"]: p for p in result.peer_data}
        bubble_data = []
        for t in all_tickers_in_group[:10]:
            pd_info = peer_lookup.get(t, {})
            mc = float(pd_info.get("market_cap", 0) or 0)
            if t == result.ticker:
                mc = result.market_cap
            role = "leader" if t in sc_group.get("leaders", []) else "follower"
            bubble_data.append(
                {
                    "ticker": t,
                    "market_cap": mc if mc > 0 else 1e9,
                    "change_pct": float(pd_info.get("change_pct", 0) or 0),
                    "role": role,
                }
            )
        if bubble_data:
            group_name = (
                sc_group.get("group", "Supply Chain Group").replace("_", " ").title()
            )
            fig = cluster_bubble(bubble_data, group_name, highlight=result.ticker)
            st.plotly_chart(fig, use_container_width=True)
    else:
        st.markdown(
            '<div class="ws-card" style="text-align:center;padding:16px;">'
            '<div style="font-size:14px;color:#64748B;">Not in a tracked supply chain group</div>'
            '<div style="font-size:12px;color:#94A3B8;margin-top:4px;">'
            "Cross-asset supply chain signals are not available for this ticker"
            "</div></div>",
            unsafe_allow_html=True,
        )

    for status, text in section.verdicts:
        st.markdown(verdict_bullet(status, text), unsafe_allow_html=True)
