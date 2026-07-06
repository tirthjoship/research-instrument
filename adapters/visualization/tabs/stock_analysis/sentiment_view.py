"""Sentiment panel (spec D12, panel #3): tone mix — THE falsified hypothesis (ADR-044 red).

ADR-044 registered the sentiment-to-return hypothesis; cross-sectional IC tests on a
clean 430-ticker universe returned ~0. The hypothesis is FALSIFIED. This panel surfaces
that result honestly: tone looks positive AND it doesn't matter.

DATA-GAP items:
- Per-source IC (computed only at universe level; by-source decomposition not wired)
- Sentiment-vs-price series: price_history IS available (see the Performance/Analyst
  panels), but buzz_signals rarely has enough distinct fetched_at days to build a
  meaningful overlay against it — the real blocker is buzz date-sparsity, not a
  missing price series.
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


def _tone_counts(buzz_signals: list[Any]) -> tuple[int, int, int]:
    """Return (positive, neutral, negative) counts using ±0.05 thresholds."""
    pos = neu = neg = 0
    for sig in buzz_signals:
        raw = getattr(sig, "sentiment_raw", None)
        try:
            r = float(raw) if raw is not None else 0.0
        except (TypeError, ValueError):
            r = 0.0
        if r > _POS_THRESHOLD:
            pos += 1
        elif r < _NEG_THRESHOLD:
            neg += 1
        else:
            neu += 1
    return pos, neu, neg


def _mean_sentiment(buzz_signals: list[Any]) -> float | None:
    """Compute mean of sentiment_raw values; None if no signals."""
    vals: list[float] = []
    for sig in buzz_signals:
        raw = getattr(sig, "sentiment_raw", None)
        try:
            vals.append(float(raw) if raw is not None else 0.0)
        except (TypeError, ValueError):
            pass
    return sum(vals) / len(vals) if vals else None


def _source_means(buzz_signals: list[Any]) -> dict[str, float]:
    """Per-source mean of sentiment_raw."""
    buckets: dict[str, list[float]] = {}
    for sig in buzz_signals:
        src = str(getattr(sig, "source", "") or "")
        raw = getattr(sig, "sentiment_raw", None)
        try:
            val = float(raw) if raw is not None else 0.0
        except (TypeError, ValueError):
            val = 0.0
        if src:
            buckets.setdefault(src, []).append(val)
    return {src: sum(vs) / len(vs) for src, vs in buckets.items()}


def _distinct_buzz_days(buzz_signals: list[Any]) -> int:
    dates = {str(getattr(sig, "fetched_at", "") or "")[:10] for sig in buzz_signals}
    dates.discard("")
    return len(dates)


_OVERLAY_MIN_DAYS = 5


def _overlay_gap_reason(result: Any, buzz_signals: list[Any]) -> str:
    """Honest reason the sentiment-vs-price overlay is a data gap.

    price_history IS available (Performance/Analyst panels use it) — the real
    blocker is that buzz_signals almost never has enough distinct days to
    plot a meaningful overlay against it, not a missing price series.
    """
    ph = getattr(result, "price_history", None) or {}
    has_price = bool(ph.get("closes")) if isinstance(ph, dict) else False
    if not has_price:
        return "no price series available"
    n_days = _distinct_buzz_days(buzz_signals)
    if n_days < _OVERLAY_MIN_DAYS:
        return f"buzz too sparse to correlate with price ({n_days} distinct day{'s' if n_days != 1 else ''} recorded, need {_OVERLAY_MIN_DAYS}+)"
    return "not yet built"


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def build_sentiment_view(result: Any) -> dict[str, Any]:
    """Build the sentiment view-model.

    Returns a dict with keys: metrics, chips, claim, reframe, verdicts.

    Six metrics:
      1. Tone mix — ratio of positive:negative (e.g. "2:1 pos")
      2. Mean score — mean of sentiment_raw values
      3. Positive count
      4. Neutral count
      5. Negative count
      6. Tested-IC — fixed "0.00 · falsified", tone=crimson (ADR-044 result; always shown)

    Chips:
      - LEANS-POSITIVE · pos:neg (grey, NOT green — IC=0 makes tone irrelevant)
      - IC=0 · falsified (crimson — ADR-044 falsified, permanent result)
    """
    buzz_signals: list[Any] = list(getattr(result, "buzz_signals", []) or [])

    pos, neu, neg = _tone_counts(buzz_signals)
    mean_val = _mean_sentiment(buzz_signals)
    has_data = bool(buzz_signals)

    ratio_str = f"{pos}:{neg}"

    metrics: list[Metric] = []

    # 1. Tone mix
    metrics.append(
        Metric(
            "tone_mix",
            "Tone mix",
            f"{pos}:{neg} pos" if has_data else _DATA_GAP,
            "pos:neg ratio" if has_data else "data gap",
            "grey",
            "Ratio of positive to negative signals using ±0.05 thresholds on sentiment_raw.",
            "count(sentiment_raw > 0.05) : count(sentiment_raw < -0.05)",
        )
    )

    # 2. Mean score
    mean_str = f"{mean_val:+.2f}" if mean_val is not None else _DATA_GAP
    metrics.append(
        Metric(
            "mean_score",
            "Mean score",
            mean_str,
            "avg sentiment_raw" if mean_val is not None else "data gap",
            "grey",
            "Mean of sentiment_raw values across all signals in this period.",
            "mean(buzz_signals[].sentiment_raw)",
        )
    )

    # 3. Positive count
    metrics.append(
        Metric(
            "positive",
            "Positive",
            str(pos) if has_data else _DATA_GAP,
            "sentiment_raw > 0.05" if has_data else "data gap",
            "grey",
            "Count of signals where sentiment_raw > 0.05.",
            "count(sentiment_raw > 0.05)",
        )
    )

    # 4. Neutral count
    metrics.append(
        Metric(
            "neutral",
            "Neutral",
            str(neu) if has_data else _DATA_GAP,
            "-0.05 to 0.05" if has_data else "data gap",
            "grey",
            "Count of signals in the neutral band where |sentiment_raw| is at most 0.05.",
            "count(|sentiment_raw| <= 0.05)",
        )
    )

    # 5. Negative count
    metrics.append(
        Metric(
            "negative",
            "Negative",
            str(neg) if has_data else _DATA_GAP,
            "sentiment_raw < -0.05" if has_data else "data gap",
            "grey",
            "Count of signals where sentiment_raw < -0.05.",
            "count(sentiment_raw < -0.05)",
        )
    )

    # 6. Tested-IC — fixed ADR-044 result; always crimson regardless of data availability
    metrics.append(
        Metric(
            "tested_ic",
            "Tested-IC",
            "0.00 · falsified",
            "ADR-044",
            "crimson",
            (
                "Cross-sectional information coefficient measured on a 430-ticker universe. "
                "IC ~0: tone does not correlate with 5-day returns. "
                "Hypothesis falsified — ADR-044."
            ),
            "cross-sectional IC, 430-ticker universe, ADR-044",
        )
    )

    # ---- Chips ----
    chips = ""

    # LEANS-POSITIVE chip: grey, NOT green — IC=0 means the lean carries no weight
    if has_data and pos >= neg:
        chips += render_status_chip(
            "LEANS-POSITIVE",
            ratio_str,
            tone="grey",
            rule=(
                f"descriptive tone mix: {pos} positive vs {neg} negative signals "
                "(+-0.05 thresholds); IC=0 per ADR-044 — lean does not imply return"
            ),
        )

    # IC=0 · falsified — always emitted; ADR-044 is a permanent falsification
    chips += render_status_chip(
        "IC=0",
        "falsified",
        tone="crimson",
        rule="cross-sectional IC ~0 on a clean 430-ticker universe, ADR-044",
    )

    overlay_gap = _overlay_gap_reason(result, buzz_signals)

    return {
        "metrics": metrics,
        "chips": chips,
        "claim": "Tone mix across monitored sources — looks positive, and it doesn't matter.",
        "reframe": (
            "ADR-044 falsified the sentiment-to-return hypothesis: tone looks positive "
            "and it doesn't matter — that candour is the product. "
            f"Sentiment-vs-price series not wired (data gap — {overlay_gap})."
        ),
        "verdicts": [
            Verdict(
                "stop",
                "IC=0 (ADR-044 falsified): tone does not drive 5-day returns on a 430-ticker universe.",
            ),
            Verdict(
                "neu",
                f"Sentiment-vs-price series not wired — data gap, {overlay_gap}.",
            ),
        ],
    }


def build_sentiment_panel(result: Any) -> str:
    """Compose the full Sentiment deep-dive panel HTML (panel #3 in Signals group)."""
    v = build_sentiment_view(result)
    buzz_signals: list[Any] = list(getattr(result, "buzz_signals", []) or [])

    # Comparison viz: tone-mix bars + by-source mean bars via panel_charts.peer_bars
    pos, neu, neg = _tone_counts(buzz_signals)
    if buzz_signals:
        tone_rows: list[tuple[str, float, bool]] = [
            ("Positive", float(pos), False),
            ("Neutral", float(neu), False),
            ("Negative", float(neg), False),
        ]
        tone_bars = panel_charts.peer_bars(tone_rows, unit=" signals")

        src_means = _source_means(buzz_signals)
        if src_means:
            src_rows: list[tuple[str, float, bool]] = [
                (src, mean, False)
                for src, mean in sorted(src_means.items(), key=lambda kv: -kv[1])
            ]
            src_bars = panel_charts.peer_bars(src_rows, unit=" mean")
        else:
            src_bars = '<div class="sa-pnl-cap">no source data</div>'

        bars_html = tone_bars + '<div style="margin-top:6px"></div>' + src_bars
    else:
        bars_html = '<div class="sa-pnl-cap">no sentiment data — data gap</div>'

    left = '<div class="sa-pnl-subh">Tone mix + by source</div>' + bars_html

    # Trend viz: sentiment-vs-price — DATA-GAP; reason is dynamic (see
    # _overlay_gap_reason) since price_history is available, buzz sparsity is
    # the actual, ticker-dependent blocker.
    overlay_gap = _overlay_gap_reason(result, buzz_signals)
    right = (
        '<div class="sa-pnl-subh">Sentiment vs price</div>'
        f'<div class="sa-pnl-cap">sentiment-vs-price series not wired — data gap ({overlay_gap})</div>'
    )

    return build_panel(
        number=3,
        name="Sentiment",
        dot_colour="#b91c1c",
        info_html=render_info(
            "Tone mix across monitored sources. "
            "ADR-044 falsified the sentiment-to-return hypothesis; IC ~0 on a 430-ticker universe.",
            "buzz_signals[].sentiment_raw (thresholds +-0.05)",
        ),
        chips_html=v["chips"],
        claim=v["claim"],
        reframe=v["reframe"],
        strip_html=_strip_html(v["metrics"]),
        viz_left=left,
        viz_right=right,
        verdicts=v["verdicts"],
        drill="open full sentiment — tone breakdown · source means · ADR-044 evidence",
    )
