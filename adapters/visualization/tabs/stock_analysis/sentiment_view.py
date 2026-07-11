"""Sentiment panel (spec D12, panel #3): tone mix — THE falsified hypothesis (ADR-044 red).

ADR-044 registered the sentiment-to-return hypothesis; cross-sectional IC tests on a
clean 430-ticker universe returned ~0. The hypothesis is FALSIFIED. This panel surfaces
that result honestly: mood may lean positive AND it doesn't matter.

DATA-GAP items:
- Per-source IC (computed only at universe level; by-source decomposition not wired)
- Sentiment-vs-price overlay when buzz has fewer than 3 distinct harvest days
"""

from __future__ import annotations

import html as _html
from typing import Any

from adapters.visualization.components import panel_charts
from adapters.visualization.components.info_tip import render_info
from adapters.visualization.components.status_chip import render_status_chip
from adapters.visualization.tabs.stock_analysis.panel import Verdict, build_panel
from adapters.visualization.tabs.stock_analysis.valuation_view import Metric

# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

_DATA_GAP = "—"

_POS_THRESHOLD = 0.05
_NEG_THRESHOLD = -0.05

_NEWS_HINTS = (
    "news",
    "rss",
    "reuters",
    "bloomberg",
    "cnbc",
    "yahoo",
    "gdelt",
    "finnhub",
)
_SOCIAL_HINTS = ("reddit", "stocktwits", "twitter", "wsb", "social")

_TONE_POS_COLOR = "#2d6a4f"
_TONE_NEU_COLOR = "#b8c4c8"
_TONE_NEG_COLOR = "#b91c1c"

_STRIP_TILE = (
    '<div class="sa-tile t-{tone}"><div class="lab">{lbl} {info}</div>'
    '<div class="num">{value}</div><div class="sub">{sub}</div></div>'
)


def _strip_html(metrics: list[Metric]) -> str:
    tiles = "".join(
        _STRIP_TILE.format(
            tone=m.tone,
            lbl=_html.escape(m.label),
            info=render_info(m.meaning, m.basis) if m.meaning else "",
            value=_html.escape(m.value),
            sub=_html.escape(m.sub),
        )
        for m in metrics
    )
    return f'<div class="sa-strip">{tiles}</div>'


def _mention_weight(sig: Any) -> int:
    return int(getattr(sig, "mention_count", 0) or 0) or 1


def _raw_sentiment(sig: Any) -> float:
    raw = getattr(sig, "sentiment_raw", None)
    try:
        return float(raw) if raw is not None else 0.0
    except (TypeError, ValueError):
        return 0.0


def _tone_weights(buzz_signals: list[Any]) -> tuple[float, float, float]:
    """Mention-weighted (positive, neutral, negative) totals."""
    pos = neu = neg = 0.0
    for sig in buzz_signals:
        cnt = float(_mention_weight(sig))
        r = _raw_sentiment(sig)
        if r > _POS_THRESHOLD:
            pos += cnt
        elif r < _NEG_THRESHOLD:
            neg += cnt
        else:
            neu += cnt
    return pos, neu, neg


def _weighted_mean_sentiment(buzz_signals: list[Any]) -> float | None:
    num = den = 0.0
    for sig in buzz_signals:
        w = float(_mention_weight(sig))
        num += _raw_sentiment(sig) * w
        den += w
    return num / den if den else None


def _pct_share(part: float, total: float) -> int:
    return round(part / total * 100) if total else 0


def _source_bucket(source: str) -> str:
    s = source.lower()
    if any(h in s for h in _SOCIAL_HINTS):
        return "social"
    if any(h in s for h in _NEWS_HINTS):
        return "news"
    return "news"


def _bucket_means(buzz_signals: list[Any]) -> dict[str, float]:
    buckets: dict[str, tuple[float, float]] = {}
    for sig in buzz_signals:
        bucket = _source_bucket(str(getattr(sig, "source", "") or ""))
        w = float(_mention_weight(sig))
        r = _raw_sentiment(sig)
        s, t = buckets.get(bucket, (0.0, 0.0))
        buckets[bucket] = (s + r * w, t + w)
    return {k: s / t for k, (s, t) in buckets.items() if t > 0}


def _daily_sentiment_series(buzz_signals: list[Any]) -> list[tuple[str, float]]:
    """Chronological (MM-DD, weighted mean sentiment) per harvest day."""
    buckets: dict[str, tuple[float, float]] = {}
    for sig in buzz_signals:
        day = str(getattr(sig, "fetched_at", "") or "")[:10]
        if not day:
            continue
        w = float(_mention_weight(sig))
        r = _raw_sentiment(sig)
        s, t = buckets.get(day, (0.0, 0.0))
        buckets[day] = (s + r * w, t + w)
    return [(day[5:], s / t if t else 0.0) for day, (s, t) in sorted(buckets.items())]


def _distinct_buzz_days(buzz_signals: list[Any]) -> int:
    dates = {str(getattr(sig, "fetched_at", "") or "")[:10] for sig in buzz_signals}
    dates.discard("")
    return len(dates)


_OVERLAY_MIN_DAYS = 3
_OVERLAY_MIN_DAYS_LIVE = 2


def _sentiment_signals(result: Any) -> list[Any]:
    """Sentiment panel rows — live or harvest, separate from buzz volume."""
    explicit = getattr(result, "sentiment_signals", None)
    if explicit:
        return list(explicit)
    return list(getattr(result, "buzz_signals", []) or [])


def _overlay_signals(result: Any, buzz_signals: list[Any]) -> list[Any]:
    """Prefer extended harvest history for overlay when 30d sentiment is sparse."""
    need = _overlay_min_days(buzz_signals)
    if _distinct_buzz_days(buzz_signals) >= need:
        return buzz_signals
    extended = list(getattr(result, "buzz_volume_signals", None) or [])
    if extended and _distinct_buzz_days(extended) >= need:
        return extended
    return buzz_signals


def _overlay_min_days(buzz_signals: list[Any]) -> int:
    if _uses_live_headlines(buzz_signals):
        return _OVERLAY_MIN_DAYS_LIVE
    return _OVERLAY_MIN_DAYS


def _overlay_gap_reason(result: Any, buzz_signals: list[Any]) -> str:
    ph = getattr(result, "price_history", None) or {}
    has_price = bool(ph.get("closes")) if isinstance(ph, dict) else False
    if not has_price:
        return "no price series available"
    overlay_rows = _overlay_signals(result, buzz_signals)
    n_days = _distinct_buzz_days(overlay_rows)
    need = _overlay_min_days(buzz_signals)
    if n_days < need:
        return (
            f"buzz too sparse to correlate with price ({n_days} distinct day"
            f"{'s' if n_days != 1 else ''} recorded, need {need}+)"
        )
    return "not yet built"


def _claim_text(
    pos_w: float,
    neg_w: float,
    mean_val: float | None,
    has_data: bool,
    *,
    stale: bool,
) -> str:
    if not has_data:
        return "No mood signal — harvest or wait."
    if stale and pos_w == 0.0 and neg_w == 0.0:
        return "Tone reads neutral from stale harvest — scorer had little to work with"
    if pos_w > neg_w and (mean_val or 0.0) > _POS_THRESHOLD:
        return "Mood leans positive — and that's all it is"
    if neg_w > pos_w and (mean_val or 0.0) < _NEG_THRESHOLD:
        return "Mood leans negative — and that's all it is"
    return "Tone reads neutral — and that's all it is"


def _publisher_label(sig: Any) -> str:
    pub = getattr(sig, "publisher", None)
    if pub:
        return str(pub).strip()[:24]
    src = str(getattr(sig, "source", "") or "").strip()
    if src in ("yfinance_headlines", ""):
        return "News"
    return src.replace("_", " ").title()[:24]


def _publisher_means(buzz_signals: list[Any]) -> dict[str, float]:
    buckets: dict[str, tuple[float, float]] = {}
    for sig in buzz_signals:
        label = _publisher_label(sig)
        w = float(_mention_weight(sig))
        r = _raw_sentiment(sig)
        s, t = buckets.get(label, (0.0, 0.0))
        buckets[label] = (s + r * w, t + w)
    return {k: s / t for k, (s, t) in buckets.items() if t > 0}


def _uses_live_headlines(buzz_signals: list[Any]) -> bool:
    return bool(buzz_signals) and all(
        getattr(s, "scorer", None) == "keyword_live" for s in buzz_signals
    )


def _summary_reframe_html(
    *,
    pos_w: float,
    neg_w: float,
    ratio_str: str,
    mean_val: float | None,
    overlay_built: bool,
    overlay_gap: str,
    live_headlines: bool = False,
) -> str:
    mean_s = f"{mean_val:+.2f}" if mean_val is not None else "+0.00"
    if pos_w == 0.0 and neg_w == 0.0:
        lead = f"Tone reads <b>neutral</b> (mean <b>{mean_s}</b>)"
    elif pos_w >= neg_w:
        lead = f"Tone ~<b>{ratio_str}</b> positive (mean <b>{mean_s}</b>)"
    else:
        lead = f"Tone ~<b>{ratio_str}</b> negative-skew (mean <b>{mean_s}</b>)"
    tail = (
        "tracks price descriptively."
        if overlay_built
        else f"sentiment-vs-price not plotted ({overlay_gap})."
    )
    if live_headlines:
        tail += " Tone from <b>live yfinance headlines</b> (keyword_live) — not harvested buzz."
    return f'<div class="sa-pnl-reline">{lead}, <b>zero tested edge</b> — {tail}</div>'


def _tone_mix_segments(
    pos_w: float, neu_w: float, neg_w: float
) -> list[tuple[str, float, str]]:
    """Percentage shares for stacked tone bar (legend matches metric tiles)."""
    total = pos_w + neu_w + neg_w or 1.0
    segs = [
        ("Positive", pos_w / total * 100.0, _TONE_POS_COLOR),
        ("Neutral", neu_w / total * 100.0, _TONE_NEU_COLOR),
        ("Negative", neg_w / total * 100.0, _TONE_NEG_COLOR),
    ]
    visible = [s for s in segs if s[1] >= 0.5]
    return visible or [("Neutral", 100.0, _TONE_NEU_COLOR)]


def _tone_mix_viz(buzz_signals: list[Any], result: Any | None = None) -> str:
    pos_w, neu_w, neg_w = _tone_weights(buzz_signals)
    if not buzz_signals:
        return '<div class="sa-pnl-cap">no sentiment data — data gap</div>'
    mix = (
        '<div class="sa-sentiment-mix">'
        + panel_charts.stacked_bar(_tone_mix_segments(pos_w, neu_w, neg_w))
        + "</div>"
    )
    publisher_source = buzz_signals
    if result is not None and not _uses_live_headlines(buzz_signals):
        extra = list(getattr(result, "sentiment_publisher_rows", None) or [])
        if extra:
            publisher_source = extra
    if _uses_live_headlines(buzz_signals) or (
        result is not None
        and list(getattr(result, "sentiment_publisher_rows", None) or [])
    ):
        pub_means = _publisher_means(publisher_source)
        rows = [
            panel_charts.sentiment_source_row(label, mean, track_width=88)
            for label, mean in sorted(pub_means.items(), key=lambda kv: -abs(kv[1]))[:4]
        ]
    else:
        bucket = _bucket_means(buzz_signals)
        rows = [
            panel_charts.sentiment_source_row(
                label, bucket[label.lower()], track_width=88
            )
            for label in ("News", "Social")
            if label.lower() in bucket
        ]
    if not rows:
        rows.append('<div class="sa-pnl-cap">no source buckets</div>')
    return mix + "".join(rows)


def _overlay_viz(result: Any, buzz_signals: list[Any]) -> tuple[str, bool]:
    overlay_gap = _overlay_gap_reason(result, buzz_signals)
    subh = '<div class="sa-pnl-subh">Sentiment vs price, 14 days</div>'
    overlay_rows = _overlay_signals(result, buzz_signals)
    daily = _daily_sentiment_series(overlay_rows)
    ph = getattr(result, "price_history", None) or {}
    closes = ph.get("closes") if isinstance(ph, dict) else None
    closes = [float(c) for c in closes] if closes else []
    min_days = _overlay_min_days(buzz_signals)
    if len(daily) >= min_days and len(closes) >= 2:
        sent_vals = [v for _, v in daily]
        chart = panel_charts.sentiment_vs_price_chart(
            sent_vals,
            closes,
            x_labels=(daily[0][0], daily[-1][0]),
        )
        if chart:
            flat_tone = all(abs(v) <= _POS_THRESHOLD for v in sent_vals)
            if flat_tone:
                cap = (
                    '<div class="sa-pnl-cap">Daily tone flat at neutral — '
                    "dashed line is trailing price only.</div>"
                )
            else:
                cap = (
                    '<div class="sa-pnl-cap">Tone (solid) shadows price (dashed) — '
                    "follows, doesn't lead.</div>"
                )
            return subh + chart + cap, True
    return (
        subh
        + f'<div class="sa-pnl-cap">sentiment-vs-price series not wired — data gap ({overlay_gap})</div>',
        False,
    )


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def build_sentiment_view(result: Any) -> dict[str, Any]:
    """Build the sentiment view-model.

    Six metrics (mockup-aligned, mention-weighted):
      Mean, Positive %, Neutral %, Negative %, Net (pos−neg), Tested IC (falsified)
    """
    buzz_signals = _sentiment_signals(result)
    stale = bool(getattr(result, "buzz_harvest_stale", False)) and not bool(
        getattr(result, "sentiment_from_live", False)
    )

    pos_w, neu_w, neg_w = _tone_weights(buzz_signals)
    total_w = pos_w + neu_w + neg_w
    mean_val = _weighted_mean_sentiment(buzz_signals)
    has_data = bool(buzz_signals)

    pos_pct = _pct_share(pos_w, total_w)
    neu_pct = _pct_share(neu_w, total_w)
    neg_pct = _pct_share(neg_w, total_w)
    net = int(round(pos_w - neg_w))
    ratio_str = f"{int(round(pos_w))}:{int(round(neg_w))}"

    metrics: list[Metric] = []

    mean_str = f"{mean_val:+.2f}" if mean_val is not None else _DATA_GAP
    metrics.append(
        Metric(
            "mean",
            "Mean",
            mean_str,
            "avg tone" if mean_val is not None else "data gap",
            "grey",
            "Mention-weighted mean of sentiment_raw across all signals in this period.",
            "sum(sentiment_raw * mention_count) / sum(mention_count)",
        )
    )

    metrics.append(
        Metric(
            "positive",
            "Positive",
            f"{pos_pct}%" if has_data else _DATA_GAP,
            "share" if has_data else "data gap",
            "grey",
            "Share of mentions classified positive (sentiment_raw > 0.05).",
            "weighted mention_count where sentiment_raw > 0.05",
        )
    )

    metrics.append(
        Metric(
            "neutral",
            "Neutral",
            f"{neu_pct}%" if has_data else _DATA_GAP,
            "share" if has_data else "data gap",
            "grey",
            "Share of mentions in the neutral band (|sentiment_raw| <= 0.05).",
            "weighted mention_count where |sentiment_raw| <= 0.05",
        )
    )

    metrics.append(
        Metric(
            "negative",
            "Negative",
            f"{neg_pct}%" if has_data else _DATA_GAP,
            "share" if has_data else "data gap",
            "grey",
            "Share of mentions classified negative (sentiment_raw < -0.05).",
            "weighted mention_count where sentiment_raw < -0.05",
        )
    )

    net_str = f"{net:+d}" if has_data else _DATA_GAP
    metrics.append(
        Metric(
            "net",
            "Net",
            net_str,
            "pos−neg" if has_data else "data gap",
            "grey",
            "Mention-weighted positive minus negative counts.",
            "sum(positive mention_count) - sum(negative mention_count)",
        )
    )

    metrics.append(
        Metric(
            "tested_ic",
            "Tested IC",
            "0.00",
            "falsified",
            "crimson",
            (
                "Cross-sectional information coefficient measured on a 430-ticker universe. "
                "IC ~0: tone does not correlate with 5-day returns. "
                "Hypothesis falsified — ADR-044."
            ),
            "cross-sectional IC, 430-ticker universe, ADR-044",
        )
    )

    chips = ""
    if has_data:
        if pos_w == 0.0 and neg_w == 0.0:
            chips += render_status_chip(
                "NEUTRAL",
                "flat",
                tone="grey",
                rule="all mention-weighted tone in neutral band; IC=0 per ADR-044",
            )
        else:
            chip_lbl = "LEANS POS" if pos_w >= neg_w else "LEANS NEG"
            chips += render_status_chip(
                chip_lbl,
                ratio_str,
                tone="grey",
                rule=(
                    f"descriptive tone mix: {int(round(pos_w))} positive vs "
                    f"{int(round(neg_w))} negative mentions (+-0.05 thresholds); "
                    "IC=0 per ADR-044 — lean does not imply return"
                ),
            )

    chips += render_status_chip(
        "IC=0",
        "falsified",
        tone="crimson",
        rule="cross-sectional IC ~0 on a clean 430-ticker universe, ADR-044",
    )

    overlay_gap = _overlay_gap_reason(result, buzz_signals)
    _, overlay_built = _overlay_viz(result, buzz_signals)

    return {
        "metrics": metrics,
        "chips": chips,
        "claim": _claim_text(pos_w, neg_w, mean_val, has_data, stale=stale),
        "reframe": (
            "ADR-044 falsified the sentiment-to-return hypothesis: mood is descriptive only."
        ),
        "reframe_html": _summary_reframe_html(
            pos_w=pos_w,
            neg_w=neg_w,
            ratio_str=ratio_str,
            mean_val=mean_val,
            overlay_built=overlay_built,
            overlay_gap=overlay_gap,
            live_headlines=_uses_live_headlines(buzz_signals),
        ),
        "verdicts": [
            Verdict(
                "stop",
                "IC=0 (ADR-044 falsified): tone has zero tested edge on 5-day returns.",
            ),
            Verdict(
                "neu" if not overlay_built else "pos",
                (
                    f"Sentiment-vs-price not plotted — data gap, {overlay_gap}."
                    if not overlay_built
                    else "Mood trails price descriptively — not a trade signal."
                ),
            ),
        ],
    }


def build_sentiment_panel(result: Any) -> str:
    """Compose the full Sentiment deep-dive panel HTML (panel #3 in Signals group)."""
    v = build_sentiment_view(result)
    buzz_signals = _sentiment_signals(result)

    left = '<div class="sa-pnl-subh">Tone mix + by source</div>' + _tone_mix_viz(
        buzz_signals, result
    )
    right, _ = _overlay_viz(result, buzz_signals)

    return build_panel(
        number=3,
        name="Sentiment",
        dot_colour="#b91c1c",
        info_html=render_info(
            "Tone mix across monitored sources. "
            "ADR-044 falsified the sentiment-to-return hypothesis; IC ~0 on a 430-ticker universe.",
            "sentiment_signals[].sentiment_raw (thresholds +-0.05), mention-weighted",
        ),
        chips_html=v["chips"],
        claim=v["claim"],
        reframe=v.get("reframe", ""),
        reframe_html=v.get("reframe_html"),
        strip_html=_strip_html(v["metrics"]),
        viz_left=left,
        viz_right=right,
        verdicts=v["verdicts"],
        drill="open full sentiment — tone breakdown · source means · ADR-044 evidence",
    )
