"""Buzz panel (spec D12): attention and volume — NEVER a directional signal.

ADR-044 pre-registered the buzz-to-return hypothesis; it was falsified.
This panel renders attention/volume data only: source mention counts, dates,
and per-source distribution.

Recent headlines prefer ``result.news_context`` (yfinance live headlines when
available). Mention log is the fallback when no real titles exist.

Mention volume chart uses a 14-day calendar window (mockup-aligned), anchored to the
latest harvest day when that is later than the analysis as-of date.
Baseline multiple is computed when >=2 distinct days exist: latest-day mentions
divided by the mean of prior recorded days (descriptive spike ratio, not a signal).
"""

from __future__ import annotations

import html as _html
from datetime import datetime, timedelta, timezone
from typing import Any

from adapters.visualization.analysis.loaders import (
    BUZZ_FALLBACK_WINDOW_DAYS,
    BUZZ_MENTION_WINDOW_DAYS,
)
from adapters.visualization.components import panel_charts
from adapters.visualization.components.info_tip import render_info
from adapters.visualization.components.status_chip import render_status_chip
from adapters.visualization.tabs.stock_analysis.panel import Verdict, build_panel
from adapters.visualization.tabs.stock_analysis.valuation_view import Metric

# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

_DATA_GAP = "—"
_ZERO = "0"
VOLUME_CHART_DAYS = 14
_HEADLINE_LIMIT = 4
_MENTION_WINDOW_SUB = f"{BUZZ_MENTION_WINDOW_DAYS}d"

_STRIP_TILE = (
    '<div class="sa-tile t-{tone}"><div class="lab">{lbl} {info}</div>'
    '<div class="num">{value}</div><div class="sub">{sub}</div></div>'
)

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

_ELEVATED_THRESHOLD = 2.0


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
    totals: dict[str, int] = {}
    for sig in buzz_signals:
        src = str(getattr(sig, "source", "") or "")
        cnt = int(getattr(sig, "mention_count", 0) or 0)
        if src:
            totals[src] = totals.get(src, 0) + cnt
    return totals


def _distinct_publishers(result: Any, buzz_signals: list[Any]) -> int:
    """Count attributed headline publishers when news_context is wired."""
    ctx = getattr(result, "news_context", None)
    if ctx is not None and not getattr(ctx, "data_gap", True):
        items = getattr(ctx, "items", None) or []
        pubs = {
            str(getattr(it, "source", "") or "").strip()
            for it in items
            if str(getattr(it, "source", "") or "").strip()
        }
        if pubs:
            return len(pubs)
    return len(_source_totals(buzz_signals))


def _day_totals(buzz_signals: list[Any]) -> dict[str, int]:
    totals: dict[str, int] = {}
    for sig in buzz_signals:
        fa = str(getattr(sig, "fetched_at", "") or "")
        if not fa:
            continue
        day = fa[:10]
        cnt = int(getattr(sig, "mention_count", 0) or 0)
        totals[day] = totals.get(day, 0) + cnt
    return totals


def _source_bucket(source: str) -> str:
    s = source.lower()
    if any(h in s for h in _SOCIAL_HINTS):
        return "social"
    if any(h in s for h in _NEWS_HINTS):
        return "news"
    return "news"


def _news_social_counts(buzz_signals: list[Any]) -> tuple[int, int]:
    news = social = 0
    for sig in buzz_signals:
        cnt = int(getattr(sig, "mention_count", 0) or 0)
        if _source_bucket(str(getattr(sig, "source", "") or "")) == "social":
            social += cnt
        else:
            news += cnt
    return news, social


def _parse_fetched_at(raw: Any) -> datetime | None:
    if raw is None:
        return None
    if isinstance(raw, datetime):
        return raw if raw.tzinfo else raw.replace(tzinfo=timezone.utc)
    s = str(raw).strip()
    if not s:
        return None
    try:
        if "T" in s:
            return datetime.fromisoformat(s.replace("Z", "+00:00"))
        return datetime.strptime(s[:10], "%Y-%m-%d").replace(tzinfo=timezone.utc)
    except ValueError:
        return None


def _reference_time(result: Any) -> datetime:
    panel = getattr(result, "analyst_panel", None)
    as_of = getattr(panel, "as_of", None) if panel is not None else None
    if as_of:
        parsed = _parse_fetched_at(as_of)
        if parsed is not None:
            return parsed
    return datetime.now(timezone.utc)


def _relative_age(dt: datetime, ref: datetime) -> str:
    secs = max(0, int((ref - dt).total_seconds()))
    if secs < 3600:
        return f"{max(1, secs // 60)}m"
    if secs < 86400:
        return f"{secs // 3600}h"
    return f"{secs // 86400}d"


def _volume_window_end(day_totals: dict[str, int], ref: datetime) -> datetime:
    """End the volume chart on the latest harvest day (sparse buzz is not wall-clock)."""
    if day_totals:
        latest_key = max(day_totals)
        return datetime.strptime(latest_key, "%Y-%m-%d").replace(tzinfo=timezone.utc)
    return ref


def _daily_window_series(
    day_totals: dict[str, int],
    ref: datetime,
    *,
    window_days: int = VOLUME_CHART_DAYS,
) -> list[tuple[str, float, str]]:
    """Calendar window ending at latest harvest or ref; missing days get 0."""
    anchor = _volume_window_end(day_totals, ref)
    end = anchor.date()
    start = end - timedelta(days=window_days - 1)
    rows: list[tuple[str, float, str]] = []
    day = start
    while day <= end:
        key = day.isoformat()
        rows.append((key[5:], float(day_totals.get(key, 0)), key))
        day += timedelta(days=1)
    return rows


def _focus_volume_rows(
    rows: list[tuple[str, float, str]],
    *,
    min_span: int = 7,
    max_span: int = 10,
) -> list[tuple[str, float, str]]:
    """Trim sparse 14-day windows to the harvest cluster (fewer empty stubs)."""
    if not rows:
        return rows
    hits = [i for i, (_, value, _) in enumerate(rows) if value > 0]
    if len(hits) > 5:
        return rows
    start = hits[0]
    end = hits[-1]
    while end - start + 1 < min_span and (start > 0 or end < len(rows) - 1):
        if start > 0:
            start -= 1
        if end < len(rows) - 1:
            end += 1
        if start == 0 and end == len(rows) - 1:
            break
    if end - start + 1 > max_span:
        start = end - max_span + 1
    return rows[start : end + 1]


def _is_synthetic_title(title: str) -> bool:
    low = title.lower()
    return " mention(s)" in low or " mention recorded" in low


def _latest_fetch(buzz_signals: list[Any]) -> datetime | None:
    latest: datetime | None = None
    for sig in buzz_signals:
        dt = _parse_fetched_at(getattr(sig, "fetched_at", None))
        if dt is not None and (latest is None or dt > latest):
            latest = dt
    return latest


def _baseline_multiple(day_totals: dict[str, int]) -> float | None:
    """Latest-day mentions / mean of prior recorded days (needs >=2 days)."""
    if len(day_totals) < 2:
        return None
    ordered = sorted(day_totals.items())
    _latest_day, latest_cnt = ordered[-1]
    prior = [cnt for _, cnt in ordered[:-1]]
    if not prior:
        return None
    baseline = sum(prior) / len(prior)
    if baseline <= 0:
        return None
    return latest_cnt / baseline


def _trend_arrow(day_totals: dict[str, int]) -> tuple[str, str, str]:
    """Return (display, sub, tone) for the Trend tile."""
    if len(day_totals) < 2:
        return (_DATA_GAP, "flat", "grey")
    ordered = sorted(day_totals.items())
    prev_cnt = ordered[-2][1]
    last_cnt = ordered[-1][1]
    if last_cnt > prev_cnt * 1.1:
        return ("▲", "rising", "amber")
    if last_cnt < prev_cnt * 0.9:
        return ("▼", "falling", "grey")
    return ("→", "flat", "grey")


def _format_source_tag(source: str) -> str:
    if not source:
        return "[—]"
    low = source.lower()
    mapping = (
        ("Reuters", ("reuters",)),
        ("Yahoo", ("yahoo",)),
        ("Reddit", ("reddit",)),
        ("Stocktwits", ("stocktwits",)),
        ("GDELT", ("gdelt",)),
        ("Google", ("google_news", "google")),
    )
    for label, keys in mapping:
        if any(k in low for k in keys):
            return f"[{label}]"
    pretty = source.replace("_", " ").title()
    return f"[{pretty[:14]}]"


def _claim_headline(
    total_mentions: int,
    baseline_multiple: float | None,
    n_sources: int,
    *,
    stale: bool = False,
    last_age: str = "",
) -> str:
    if total_mentions <= 0:
        return "No monitored attention recorded — descriptive only."
    if stale:
        age = last_age or _DATA_GAP
        return (
            f"Last harvest {age} ago — outside {BUZZ_MENTION_WINDOW_DAYS}d window, "
            "descriptive only."
        )
    if baseline_multiple is not None and baseline_multiple >= _ELEVATED_THRESHOLD:
        return "Loud right now — attention spike, not a trade call"
    if n_sources >= 2 or total_mentions >= 10:
        return "Some attention across sources — descriptive only."
    return "Quiet on monitored sources — descriptive only."


def _summary_reframe_html(
    *,
    total_mentions: int,
    n_sources: int,
    baseline_multiple: float | None,
    stale: bool = False,
    last_age: str = "",
) -> str:
    if total_mentions <= 0:
        return (
            "No mention data in the monitored window. "
            "Buzz-to-return was <b>falsified</b> (ADR-044)."
        )
    if stale:
        age = last_age or _DATA_GAP
        parts = [
            (
                f"No harvest in last <b>{BUZZ_MENTION_WINDOW_DAYS}d</b> — showing "
                f"last recorded batch (<b>{age}</b> ago): "
                f"<b>{total_mentions}</b> mentions, <b>{n_sources}</b> sources"
            )
        ]
    else:
        parts = [
            (
                f"<b>{total_mentions}</b> mentions across <b>{n_sources}</b> sources "
                f"(last <b>{BUZZ_MENTION_WINDOW_DAYS}d</b>)"
            )
        ]
    if baseline_multiple is not None:
        parts.append(f"latest day <b>{baseline_multiple:.1f}×</b> prior daily mean")
    parts.append("buzz→return was <b>falsified</b> (ADR-044)")
    return ", ".join(parts[:-1]) + f"; {parts[-1]}."


def _headline_row(
    src_tag: str,
    title_html: str,
    age: str,
    *,
    src_full: str = "",
    title_full: str = "",
    url: str = "",
) -> str:
    src_tip = (
        f' title="{_html.escape(src_full)}"'
        if src_full and src_full != src_tag.strip("[]")
        else ""
    )
    title_tip = f' title="{_html.escape(title_full)}"' if title_full else ""
    safe_url = url.strip()
    if safe_url.startswith(("http://", "https://")):
        title_cell = (
            f'<a class="sa-buzz-link" href="{_html.escape(safe_url)}" '
            f'target="_blank" rel="noopener noreferrer"{title_tip}>'
            f"{title_html}</a>"
        )
    else:
        title_cell = f'<span class="ti"{title_tip}>{title_html}</span>'
    return (
        '<div class="sa-buzz-hl">'
        f'<span class="src"{src_tip}>{_html.escape(src_tag)}</span>'
        f"{title_cell}"
        f'<span class="dt">{_html.escape(age)}</span>'
        "</div>"
    )


def _headline_block(rows: list[str], extra_rows: list[str]) -> str:
    """Visible headlines plus optional expandable remainder."""
    if not extra_rows:
        return "".join(rows)
    n = len(extra_rows)
    word = "headlines" if n != 1 else "headline"
    return (
        "".join(rows)
        + f'<details class="sa-buzz-more"><summary>+ {n} more {word}</summary>'
        + "".join(extra_rows)
        + "</details>"
    )


def _mention_log_html(buzz_signals: list[Any], ref: datetime) -> str:
    if not buzz_signals:
        return '<div class="sa-pnl-cap">0 mentions recorded</div>'
    sorted_sigs = sorted(
        buzz_signals,
        key=lambda s: _parse_fetched_at(getattr(s, "fetched_at", None))
        or datetime.min.replace(tzinfo=timezone.utc),
        reverse=True,
    )
    rows: list[str] = []
    for sig in sorted_sigs[:_HEADLINE_LIMIT]:
        src = _format_source_tag(str(getattr(sig, "source", "") or ""))
        cnt = int(getattr(sig, "mention_count", 0) or 0)
        dt = _parse_fetched_at(getattr(sig, "fetched_at", None))
        age = _relative_age(dt, ref) if dt else _DATA_GAP
        word = "mentions" if cnt != 1 else "mention"
        text = _html.escape(f"{cnt} {word} recorded")
        rows.append(_headline_row(src, text, age))
    cap = (
        '<div class="sa-pnl-cap">Attributed mention log — source and count, '
        "not scored for direction.</div>"
    )
    return "".join(rows) + cap


def _headlines_html(result: Any, buzz_signals: list[Any], ref: datetime) -> str:
    """Prefer real headlines from news_context; fall back to mention log."""
    age_ref = datetime.now(timezone.utc)
    ctx = getattr(result, "news_context", None)
    items: list[Any] = []
    if ctx is not None and not getattr(ctx, "data_gap", True):
        items = [
            it
            for it in (getattr(ctx, "items", None) or [])
            if not _is_synthetic_title(str(getattr(it, "title", "") or ""))
        ]
    if not items:
        return _mention_log_html(buzz_signals, ref)

    rows: list[str] = []
    for item in items:
        raw_src = str(getattr(item, "source", "") or "")
        src = _format_source_tag(raw_src)
        plain_title = str(getattr(item, "title", "") or "")
        title = _html.escape(plain_title)
        date_str = str(getattr(item, "date", "") or "")
        dt = _parse_fetched_at(date_str)
        age = _relative_age(dt, age_ref) if dt is not None else _DATA_GAP
        rows.append(
            _headline_row(
                src,
                title,
                age,
                src_full=raw_src,
                title_full=plain_title,
                url=str(getattr(item, "url", "") or ""),
            )
        )
    cap = (
        '<div class="sa-pnl-cap">Attributed, linked — context, not signal '
        "(ADR-056).</div>"
    )
    return _headline_block(rows[:_HEADLINE_LIMIT], rows[_HEADLINE_LIMIT:]) + cap


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def build_buzz_view(result: Any) -> dict[str, Any]:
    """Build the buzz view-model.

    Six metrics (mockup-aligned):
      1. Mentions — total count (0 when empty)
      2. Sources — distinct platforms (0 when empty)
      3. vs base — spike ratio vs prior-day mean (— when <2 days)
      4. Last — relative age of latest fetch (— when unknown)
      5. News/soc — mention split news/social (0/0 when empty)
      6. Trend — ▲/▼/→ from last two recorded days (— when <2 days)
    """
    buzz_signals: list[Any] = list(getattr(result, "buzz_signals", []) or [])
    volume_signals: list[Any] = list(
        getattr(result, "buzz_volume_signals", None) or buzz_signals
    )
    volume_extended = bool(getattr(result, "buzz_volume_extended", False))
    stale = bool(getattr(result, "buzz_harvest_stale", False))
    ref = _reference_time(result)

    totals = _source_totals(buzz_signals)
    total_mentions = sum(totals.values())
    n_sources = _distinct_publishers(result, buzz_signals)
    n_platforms = len(totals)
    volume_day_totals = _day_totals(volume_signals)
    news_cnt, social_cnt = _news_social_counts(buzz_signals)
    baseline = _baseline_multiple(volume_day_totals)
    latest = _latest_fetch(buzz_signals)
    last_age = _relative_age(latest, ref) if latest is not None else _DATA_GAP
    trend_val, trend_sub, trend_tone = _trend_arrow(volume_day_totals)
    mention_sub = "stale" if stale else _MENTION_WINDOW_SUB
    mention_tone = "amber" if stale else "grey"

    # ---- 6 metrics (0 or — fallbacks) ----
    metrics: list[Metric] = [
        Metric(
            "mentions",
            "Mentions",
            str(total_mentions) if buzz_signals else _ZERO,
            mention_sub,
            mention_tone,
            (
                f"Total mention count across monitored sources in the last "
                f"{BUZZ_MENTION_WINDOW_DAYS} days."
                + (" Showing last harvest outside that window." if stale else "")
            ),
            (
                f"sum(buzz_signals[].mention_count) where fetched_at is within "
                f"{BUZZ_MENTION_WINDOW_DAYS}d of analysis time"
                + (
                    "; stale fallback from last harvest within "
                    f"{BUZZ_FALLBACK_WINDOW_DAYS}d"
                    if stale
                    else ""
                )
            ),
        ),
        Metric(
            "sources",
            "Sources",
            str(n_sources) if buzz_signals else _ZERO,
            "publishers" if n_sources and n_sources != n_platforms else "tracked",
            "grey",
            (
                "Distinct headline publishers when yfinance headlines are available; "
                "otherwise distinct harvest platforms with mention counts."
            ),
            (
                "count(distinct news_context.items[].source) when wired; "
                "else count(distinct buzz_signals[].source)"
            ),
        ),
        Metric(
            "vs_base",
            "vs base",
            f"{baseline:.1f}×" if baseline is not None else _DATA_GAP,
            (
                "spike"
                if baseline is not None and baseline >= _ELEVATED_THRESHOLD
                else "ratio"
            ),
            (
                "amber"
                if baseline is not None and baseline >= _ELEVATED_THRESHOLD
                else "grey"
            ),
            (
                "Latest recorded day divided by the mean of prior recorded days. "
                "Descriptive attention spike ratio — not a trade call."
            ),
            "latest_day_mentions / mean(prior_day_mentions); needs >=2 distinct days"
            + (
                "; uses 90d volume extension when 30d is sparse"
                if volume_extended
                else ""
            ),
        ),
        Metric(
            "last",
            "Last",
            _relative_age(latest, ref) if latest is not None else _DATA_GAP,
            "fresh" if latest is not None else "unknown",
            "grey",
            "How recently mention data was last fetched.",
            "max(buzz_signals[].fetched_at) vs analysis as-of",
        ),
        Metric(
            "news_soc",
            "News/soc",
            f"{news_cnt}/{social_cnt}",
            "mix",
            "grey",
            "Mention counts split by news-like vs social-like source heuristics.",
            "sum(mention_count) by source bucket",
        ),
        Metric(
            "trend",
            "Trend",
            trend_val,
            trend_sub,
            trend_tone,
            "Direction of mention volume between the last two recorded days.",
            "compare last two distinct fetched_at days",
        ),
    ]

    # ---- Chips ----
    chips = ""
    if baseline is not None and baseline >= _ELEVATED_THRESHOLD:
        chips += render_status_chip(
            "ELEVATED",
            f"{baseline:.1f}×",
            tone="amber",
            rule=(
                f"latest day ≥{_ELEVATED_THRESHOLD:.0f}× the mean of prior recorded days — "
                "attention spike; descriptive only, not a trade call"
            ),
        )
    chip_total = str(total_mentions) if buzz_signals else _ZERO
    chip_src = str(n_sources) if buzz_signals else _ZERO
    chips += render_status_chip(
        "",
        f"{chip_total} · {chip_src} src",
        tone="grey",
        rule=(
            f"total mentions and distinct source count in the last "
            f"{BUZZ_MENTION_WINDOW_DAYS}-day harvest window"
        ),
    )

    elevated = baseline is not None and baseline >= _ELEVATED_THRESHOLD
    verdicts = [
        Verdict(
            "cau" if elevated else "neu",
            (
                "Attention spike vs prior recorded days — buzz→return falsified, no edge."
                if elevated
                else "Mention volume shown for context — buzz→return falsified (ADR-044)."
            ),
        ),
        Verdict(
            "neu",
            (
                f"News/social mix {news_cnt}/{social_cnt} — attributed counts only."
                if buzz_signals
                else "No mention data in the monitored window."
            ),
        ),
    ]

    return {
        "metrics": metrics,
        "chips": chips,
        "claim": _claim_headline(
            total_mentions,
            baseline,
            n_sources,
            stale=stale,
            last_age=last_age,
        ),
        "reframe": "",
        "reframe_html": _summary_reframe_html(
            total_mentions=total_mentions,
            n_sources=n_sources,
            baseline_multiple=baseline,
            stale=stale,
            last_age=last_age,
        ),
        "verdicts": verdicts,
    }


def _volume_section_html(
    buzz_signals: list[Any],
    ref: datetime,
    *,
    volume_extended: bool = False,
) -> str:
    """Mention-volume chart block for the buzz split layout."""
    day_totals = _day_totals(buzz_signals)
    if not day_totals:
        return (
            f'<div class="sa-pnl-subh">Mention volume, {VOLUME_CHART_DAYS} days</div>'
            '<div class="sa-pnl-cap">0 mentions — no volume series to chart.</div>'
        )
    anchor = _volume_window_end(day_totals, ref)
    day_rows = _focus_volume_rows(_daily_window_series(day_totals, ref))
    sparse = sum(1 for _, v, _ in day_rows if v > 0) <= 4
    vol = panel_charts.volume_bars(
        day_rows,
        css_class="sa-buzz-vol",
        compact=sparse,
    )
    recorded = len(day_totals)
    span = len(day_rows)
    cap = (
        f'<div class="sa-pnl-cap">{span}-day harvest window ending '
        f"{anchor.date().isoformat()} — "
        f"{recorded} day{'s' if recorded != 1 else ''} with mentions."
        + (
            f" Extended to {BUZZ_FALLBACK_WINDOW_DAYS}d for volume context "
            f"(30d window is single-day sparse)."
            if volume_extended
            else ""
        )
        + "</div>"
    )
    wrap_cls = (
        "sa-buzz-chart-wrap sa-buzz-chart-wrap--sparse"
        if sparse
        else "sa-buzz-chart-wrap"
    )
    return (
        f'<div class="sa-pnl-subh">Mention volume, {span} days</div>'
        f'<div class="{wrap_cls}">' + vol + "</div>" + cap
    )


def build_buzz_panel(result: Any) -> str:
    """Compose the full Buzz deep-dive panel HTML (panel #2 in Signals group)."""
    v = build_buzz_view(result)
    buzz_signals: list[Any] = list(getattr(result, "buzz_signals", []) or [])
    volume_signals: list[Any] = list(
        getattr(result, "buzz_volume_signals", None) or buzz_signals
    )
    volume_extended = bool(getattr(result, "buzz_volume_extended", False))
    ref = _reference_time(result)

    headlines = '<div class="sa-pnl-subh">Recent headlines</div>' + _headlines_html(
        result, buzz_signals, ref
    )
    chart = _volume_section_html(
        volume_signals,
        ref,
        volume_extended=volume_extended,
    )
    body = (
        '<div class="sa-buzz-split">'
        f'<div class="sa-buzz-news-col">{headlines}</div>'
        f'<div class="sa-buzz-vol-col">{chart}</div>'
        "</div>"
    )

    return build_panel(
        number=2,
        name="Buzz",
        dot_colour="#5c6bc0",
        info_html=render_info(
            "Attention and volume across monitored platforms. "
            "ADR-044 falsified buzz-to-return; attention only, never a trade call.",
            "buzz_signals[].source + mention_count + fetched_at",
        ),
        chips_html=v["chips"],
        claim=v["claim"],
        reframe=v.get("reframe", ""),
        reframe_html=v.get("reframe_html"),
        strip_html=_strip_html(v["metrics"]),
        viz_left=body,
        viz_right="",
        verdicts=v["verdicts"],
        drill="open full buzz — mention history · source breakdown · volume trend",
    )
