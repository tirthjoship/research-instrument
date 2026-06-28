"""Buzz panel (spec D12): attention and volume signals — NEVER a directional signal.

ADR-044 pre-registered the buzz-to-return hypothesis; it was falsified.
This panel renders attention/volume data only: source mention counts, dates,
and per-source distribution.

DATA-GAP items:
- Baseline multiple (no historical baseline wired — ELEVATED chip never emitted)
- Mention-volume trend (no time-series wired)
- Real headline text (BuzzSignal has no titles; summaries show source+count+date only)
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


def _source_totals(buzz_signals: list[Any]) -> dict[str, int]:
    """Aggregate mention_count per source."""
    totals: dict[str, int] = {}
    for sig in buzz_signals:
        src = str(getattr(sig, "source", "") or "")
        cnt = int(getattr(sig, "mention_count", 0) or 0)
        if src:
            totals[src] = totals.get(src, 0) + cnt
    return totals


def _mention_summaries_html(buzz_signals: list[Any]) -> str:
    """Render per-signal mention summaries (attributed source + count + date).

    These are mention summaries, not headlines — BuzzSignal carries no title.
    Direction is NOT scored here; data is presented as-is.
    """
    if not buzz_signals:
        return '<div class="sa-pnl-cap">no mention data</div>'
    rows: list[str] = []
    for sig in buzz_signals[:8]:  # cap display at 8 entries
        src = _html.escape(str(getattr(sig, "source", "") or ""))
        cnt = int(getattr(sig, "mention_count", 0) or 0)
        fa = str(getattr(sig, "fetched_at", "") or "")
        date = _html.escape(fa[:10]) if fa else "—"
        rows.append(
            "<div style=\"font-family:'IBM Plex Mono',monospace;font-size:9.5px;"
            'margin:3px 0;color:var(--ri-ink2)">'
            f"{src} &nbsp;·&nbsp; {cnt} mentions &nbsp;·&nbsp; {date}"
            "</div>"
        )
    return "".join(rows)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def build_buzz_view(result: Any) -> dict[str, Any]:
    """Build the buzz view-model.

    Returns a dict with keys: metrics, chips, claim, reframe, verdicts.

    Six metrics:
      1. Total mentions (sum of mention_count across all signals)
      2. Sources (count of distinct source platforms)
      3. Top source (platform with the highest total mention count)
      4. Distinct days (count of distinct fetched_at[:10] calendar dates)
      5. Latest date (most recent fetched_at date)
      6. Baseline multiple (DATA-GAP — no historical baseline wired)

    Chips: ACTIVE · N sources (grey, descriptive only).
    No ELEVATED chip is ever emitted — no baseline exists to compare against.
    ADR-044 falsified buzz-to-return; attention only, never a signal.
    """
    buzz_signals: list[Any] = list(getattr(result, "buzz_signals", []) or [])

    totals = _source_totals(buzz_signals)
    total_mentions = sum(totals.values())
    n_sources = len(totals)

    # Top source by total mentions
    top_source: str | None = max(totals, key=lambda k: totals[k]) if totals else None

    # Distinct calendar days
    dates: set[str] = set()
    for sig in buzz_signals:
        fa = str(getattr(sig, "fetched_at", "") or "")
        if fa:
            dates.add(fa[:10])
    n_days = len(dates)
    latest_date: str | None = max(dates) if dates else None

    has_data = bool(buzz_signals)

    # ---- 6 metrics ----
    metrics: list[Metric] = []

    # 1. Total mentions
    metrics.append(
        Metric(
            "total_mentions",
            "Total mentions",
            str(total_mentions) if has_data else _DATA_GAP,
            "sum across sources" if has_data else "data gap",
            "grey",
            "Total mention count aggregated across all monitored sources in this period.",
            "sum(buzz_signals[].mention_count)",
        )
    )

    # 2. Sources
    metrics.append(
        Metric(
            "sources",
            "Sources",
            str(n_sources) if has_data else _DATA_GAP,
            "distinct platforms" if has_data else "data gap",
            "grey",
            "Number of distinct platforms contributing mention counts.",
            "count(distinct buzz_signals[].source)",
        )
    )

    # 3. Top source
    top_sub = f"{totals[top_source]} mentions" if top_source else "data gap"
    metrics.append(
        Metric(
            "top_source",
            "Top source",
            top_source if top_source else _DATA_GAP,
            top_sub,
            "grey",
            "Platform with the highest total mention count in this period.",
            "argmax(buzz_signals[].source by mention_count)",
        )
    )

    # 4. Distinct days
    metrics.append(
        Metric(
            "distinct_days",
            "Distinct days",
            str(n_days) if dates else _DATA_GAP,
            "days active" if dates else "data gap",
            "grey",
            "Number of distinct calendar days on which mentions were recorded.",
            "count(distinct buzz_signals[].fetched_at[:10])",
        )
    )

    # 5. Latest date
    metrics.append(
        Metric(
            "latest_date",
            "Latest date",
            latest_date if latest_date else _DATA_GAP,
            "most recent fetch" if latest_date else "data gap",
            "grey",
            "Most recent calendar date on which mention data was fetched.",
            "max(buzz_signals[].fetched_at[:10])",
        )
    )

    # 6. Baseline multiple — DATA-GAP (no historical baseline wired)
    metrics.append(
        Metric(
            "baseline_multiple",
            "Baseline multiple",
            _DATA_GAP,
            "data gap",
            "grey",
            (
                "Ratio of current mentions to a historical baseline period. "
                "No baseline period is wired — this value is always data gap."
            ),
            "data gap — no historical baseline wired",
        )
    )

    # ---- Chips ----
    # Only emit ACTIVE when data is present. Never emit ELEVATED (no baseline).
    chips = ""
    if has_data and n_sources > 0:
        chips += render_status_chip(
            "ACTIVE",
            f"{n_sources} sources",
            tone="grey",
            rule=(
                "descriptive: at least one source returned mention data this period; "
                "no historical baseline exists — volume level is not assessed"
            ),
        )

    return {
        "metrics": metrics,
        "chips": chips,
        "claim": "Attention and volume across monitored platforms — descriptive only.",
        "reframe": (
            "Buzz-to-return hypothesis falsified (ADR-044); attention only, never a signal. "
            "Baseline multiple and mention-volume trend are not wired (data gap). "
            "Mention summaries show attributed source and count, not scored items."
        ),
        "verdicts": [
            Verdict(
                "neu",
                "Mention-volume trend not wired — data gap, no time-series available.",
            ),
            Verdict(
                "neu",
                "Baseline multiple not wired — data gap, no historical comparison available.",
            ),
        ],
    }


def build_buzz_panel(result: Any) -> str:
    """Compose the full Buzz deep-dive panel HTML (panel #2 in Signals group)."""
    v = build_buzz_view(result)
    buzz_signals: list[Any] = list(getattr(result, "buzz_signals", []) or [])

    # Comparison viz: per-source mention bars via panel_charts.peer_bars
    totals = _source_totals(buzz_signals)
    if totals:
        rows: list[tuple[str, float, bool]] = [
            (src, float(cnt), False)
            for src, cnt in sorted(totals.items(), key=lambda kv: -kv[1])
        ]
        bars_html = panel_charts.peer_bars(rows, unit=" mentions")
    else:
        bars_html = '<div class="sa-pnl-cap">no buzz data — data gap</div>'

    left = '<div class="sa-pnl-subh">Mentions by source</div>' + bars_html

    # Trend viz: mention-volume — DATA-GAP (no time-series wired)
    summaries_html = _mention_summaries_html(buzz_signals)
    right = (
        '<div class="sa-pnl-subh">Mention-volume trend</div>'
        '<div class="sa-pnl-cap">mention-volume trend not wired — data gap</div>'
        '<div class="sa-pnl-subh" style="margin-top:8px">Mention summaries</div>'
        + summaries_html
    )

    return build_panel(
        number=2,
        name="Buzz",
        dot_colour="#5c6bc0",
        info_html=render_info(
            "Attention and volume across monitored platforms. "
            "ADR-044 falsified buzz-to-return; attention only, never a signal.",
            "buzz_signals[].source + mention_count + fetched_at",
        ),
        chips_html=v["chips"],
        claim=v["claim"],
        reframe=v["reframe"],
        strip_html=_strip_html(v["metrics"]),
        viz_left=left,
        viz_right=right,
        verdicts=v["verdicts"],
        drill="open full buzz — mention history · source breakdown · volume trend",
    )
