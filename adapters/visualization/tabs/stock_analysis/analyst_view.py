"""Analyst panel (spec D12): context-only — reports the Street's mean rating and targets.

This panel reports third-party analyst ratings and price targets as facts.
It does NOT adopt, endorse, or echo analyst recommendations as the project's view.
All tone is petrol (never green): the data is attributed to the Street, not the model.

DATA-GAP items: the 90-day target and EPS-estimate revision *history* (no
timestamped estimate series available) — those slots show the current implied
upside to the mean target and the consensus forward EPS instead. The trend viz
uses the price_history already fetched for the Performance panel plotted
against the mean target — it is a price/target comparison, not a target
history (still a data gap without price_history).
"""

from __future__ import annotations

import html as _html
from typing import Any

from adapters.visualization.components import panel_charts
from adapters.visualization.components.currency import (
    currency_for_ticker,
    currency_symbol,
)
from adapters.visualization.components.info_tip import render_info
from adapters.visualization.components.status_chip import render_status_chip
from adapters.visualization.tabs.stock_analysis.panel import Verdict, build_panel
from adapters.visualization.tabs.stock_analysis.valuation_view import Metric

# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

_STRIP_TILE = (
    '<div class="sa-tile t-{tone}"><div class="lab">{lbl} {info}</div>'
    '<div class="num">{value}</div><div class="sub">{sub}</div></div>'
)

_DATA_GAP = "—"

# Slop-safe tier labels (r1..r5) — mockup-style names are FORBIDDEN_WORDS in output.
_RATING_TIER_LABELS: dict[int, str] = {
    1: "Str. pos.",
    2: "Positive",
    3: "Hold",
    4: "Reduce",
    5: "Negative",
}
_RATING_POS_COLOR = "#7d89c4"
_RATING_NEU_COLOR = "#c2ccce"


def _consensus_sub(mean_rating: float) -> str:
    if mean_rating <= 2.0:
        return "positive"
    if mean_rating <= 3.0:
        return "neutral"
    return "cautious"


def _claim_headline(mean_rating: float | None) -> str:
    if mean_rating is None:
        return "Street analyst consensus — third-party context only."
    if mean_rating <= 2.0:
        return "Street leans positive — but that's their view, not ours"
    if mean_rating <= 3.0:
        return "Street is mixed — their view, not ours"
    return "Street leans cautious — their view, not ours"


def _summary_reframe_html(
    *,
    count: int,
    mean_rating: float | None,
    target_mean: float | None,
    upside_pct: float | None,
    target_low: float | None,
    target_high: float | None,
    is_wide: bool,
    ticker: str = "",
) -> str:
    """Mockup-style one-line data summary with bold key figures."""
    e = _html.escape
    sym = currency_symbol(currency_for_ticker(ticker))
    parts: list[str] = []
    if count:
        parts.append(f"{e(str(count))} analysts")
    if mean_rating is not None:
        parts.append(f"consensus <b>{mean_rating:.1f}</b>")
    if target_mean is not None:
        tgt = f"mean target <b>{sym}{target_mean:.0f}</b>"
        if upside_pct is not None:
            sign = "+" if upside_pct >= 0 else ""
            tgt += f" ({sign}{upside_pct:.0f}%)"
        parts.append(tgt)
    if target_low is not None and target_high is not None:
        tail = (
            f"Spread <b>{sym}{target_low:.0f}–{sym}{target_high:.0f}</b> — real disagreement."
            if is_wide
            else f"Target range <b>{sym}{target_low:.0f}–{sym}{target_high:.0f}</b>."
        )
        parts.append(tail)
    if not parts:
        return "Analyst ratings and targets reported as third-party context."
    return ", ".join(parts[:-1]) + (", " + parts[-1] if len(parts) > 1 else parts[0])


def _rating_distribution_rows(rd: dict[str, int]) -> list[tuple[str, float, str]]:
    rows: list[tuple[str, float, str]] = []
    for tier in range(1, 6):
        cnt = float(rd.get(f"r{tier}", 0) or 0)
        if cnt <= 0:
            continue
        color = _RATING_POS_COLOR if tier <= 2 else _RATING_NEU_COLOR
        rows.append((_RATING_TIER_LABELS[tier], cnt, color))
    return rows


def _distribution_skew_caption(rd: dict[str, int]) -> str:
    pos = float(rd.get("r1", 0) or 0) + float(rd.get("r2", 0) or 0)
    other = sum(float(rd.get(f"r{i}", 0) or 0) for i in range(3, 6))
    if pos > other and pos > 0:
        return "Skewed positive — but targets disagree on how much."
    if other > pos and other > 0:
        return "Ratings mixed — consensus hides real target disagreement."
    return "Rating distribution across contributing analysts."


def _analyst_context_verdict(count: int, mean_rating: float | None) -> str:
    if count and mean_rating is not None and mean_rating <= 2.5:
        return f"{count} analysts lean positive — third-party context."
    if count:
        return f"{count} analysts covering — third-party context."
    return "Analyst consensus reported — third-party context."


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


def _upside_metric(target_mean: float | None, current_price: float | None) -> Metric:
    """Implied upside/downside to the Street's mean target. Petrol tone — it is
    the Street's view (target), reported not adopted, so never green/amber."""
    meaning = (
        "Implied move to the analyst consensus mean target: (mean target − price) / price. "
        "This is the Street's view, reported as context — not adopted as the project's call."
    )
    basis = "(analyst_panel.target_mean − current_price) / current_price; third-party"
    if target_mean is None or not current_price:
        return Metric("upside", "Upside", _DATA_GAP, "data gap", "grey", meaning, basis)
    pct = (target_mean - current_price) / current_price * 100
    return Metric(
        "upside",
        "Upside",
        f"{pct:+.0f}%",
        "to mean target",
        "petrol",
        meaning,
        basis,
    )


def _fwd_eps_metric(info: dict[str, Any], ticker: str = "") -> Metric:
    """Consensus forward EPS estimate — an analyst output we do have, in place of
    the unavailable 90-day EPS-estimate history. Petrol tone (Street's estimate)."""
    meaning = (
        "Consensus forward earnings-per-share estimate (next fiscal year). "
        "A third-party analyst estimate, reported as context — not adopted."
    )
    basis = "yfinance info.forwardEps; Street consensus; reported not adopted"
    eps = _safe_float((info or {}).get("forwardEps"))
    if eps is None:
        return Metric(
            "fwd_eps", "Fwd EPS", _DATA_GAP, "data gap", "grey", meaning, basis
        )
    sym = currency_symbol(currency_for_ticker(ticker))
    return Metric(
        "fwd_eps",
        "Fwd EPS",
        f"{sym}{eps:.2f}",
        "consensus est",
        "petrol",
        meaning,
        basis,
    )


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def build_analyst_view(result: Any) -> dict[str, Any]:
    """Build the analyst view-model.

    Returns a dict with keys: metrics, chips, claim, reframe, verdicts.

    Six metrics:
      1. Analysts (count)
      2. Consensus (mean_rating, e.g. 1.6)
      3. Mean target (target_mean in dollars)
      4. Dispersion (target_high − target_low; amber when wide ≥ 30% of mean target)
      5. Upside (implied move to the mean target; petrol — Street's view)
      6. Fwd EPS (consensus forward EPS estimate; petrol — Street's view)

    Chips use petrol tone only — the Street's ratings are reported, not adopted.
    """
    panel = getattr(result, "analyst_panel", None)
    ticker = getattr(result, "ticker", "")
    sym = currency_symbol(currency_for_ticker(ticker))

    # If no panel or explicit data_gap, degrade all metrics
    if panel is None or getattr(panel, "data_gap", False):
        metrics: list[Metric] = [
            Metric(
                "analysts",
                "Analysts",
                _DATA_GAP,
                "data gap",
                "grey",
                "Number of analysts contributing to the consensus estimate.",
                "analyst_panel.count — data gap",
            ),
            Metric(
                "consensus",
                "Consensus",
                _DATA_GAP,
                "data gap",
                "grey",
                "Mean analyst rating on a 1–5 scale where 1 = most positive, 5 = most negative. "
                "Third-party Street rating; reported not adopted.",
                "analyst_panel.mean_rating — data gap",
            ),
            Metric(
                "mean_target",
                "Mean target",
                _DATA_GAP,
                "data gap",
                "grey",
                "Analyst consensus mean price target in USD.",
                "analyst_panel.target_mean — data gap",
            ),
            Metric(
                "dispersion",
                "Dispersion",
                _DATA_GAP,
                "data gap",
                "grey",
                "Spread between the highest and lowest analyst price targets. "
                "Wide dispersion (≥30% of mean target) signals real disagreement the consensus hides.",
                "analyst_panel.target_high − target_low — data gap",
            ),
            Metric(
                "upside",
                "Upside",
                _DATA_GAP,
                "data gap",
                "grey",
                "Implied move to the analyst consensus mean target; needs a target and price.",
                "data gap — analyst target unavailable",
            ),
            Metric(
                "fwd_eps",
                "Fwd EPS",
                _DATA_GAP,
                "data gap",
                "grey",
                "Consensus forward EPS estimate; a third-party analyst estimate.",
                "data gap — forward EPS unavailable",
            ),
        ]
        chips = render_status_chip(
            "ANALYST DATA",
            "unavailable",
            tone="grey",
            rule="analyst_panel.data_gap is True — no analyst data available for this ticker",
        )
        return {
            "metrics": metrics,
            "chips": chips,
            "claim": "Analyst data not available for this ticker.",
            "reframe": (
                "No analyst data wired for this ticker. "
                "Wide dispersion = real disagreement the consensus hides."
            ),
            "reframe_html": None,
            "verdicts": [
                Verdict("neu", "Analyst data unavailable — data gap for this ticker."),
            ],
        }

    count: int = getattr(panel, "count", 0) or 0
    mean_rating: float | None = _safe_float(getattr(panel, "mean_rating", None))
    target_mean: float | None = _safe_float(getattr(panel, "target_mean", None))
    target_high: float | None = _safe_float(getattr(panel, "target_high", None))
    target_low: float | None = _safe_float(getattr(panel, "target_low", None))

    # 1. Analysts (count)
    analysts_meaning = "Number of analysts contributing to the consensus estimate."
    analysts_basis = "analyst_panel.count"
    m_analysts = Metric(
        "analysts",
        "Analysts",
        str(count) if count else _DATA_GAP,
        "covering" if count else "data gap",
        "grey",
        analysts_meaning,
        analysts_basis,
    )

    # 2. Consensus (mean_rating, 1–5 scale, 1 = most positive)
    consensus_meaning = (
        "Mean analyst rating on a 1–5 scale where 1 = most positive and 5 = most negative. "
        "This is the Street's third-party consensus; it is reported here, not adopted as the project's view."
    )
    consensus_basis = "analyst_panel.mean_rating; 1=most positive … 5=most negative; third-party, not adopted"
    if mean_rating is None:
        m_consensus = Metric(
            "consensus",
            "Consensus",
            _DATA_GAP,
            "data gap",
            "grey",
            consensus_meaning,
            consensus_basis,
        )
    else:
        m_consensus = Metric(
            "consensus",
            "Consensus",
            f"{mean_rating:.1f}",
            _consensus_sub(mean_rating),
            "petrol",
            consensus_meaning,
            consensus_basis,
        )

    current_price = _safe_float(getattr(result, "current_price", None))
    upside_pct: float | None = None
    if target_mean is not None and current_price:
        upside_pct = (target_mean - current_price) / current_price * 100

    # 3. Mean target — upside % in sub (mockup combines mean tgt + implied move)
    mean_target_meaning = "Analyst consensus mean price target in USD."
    mean_target_basis = (
        "analyst_panel.target_mean; Street price target; third-party, not adopted"
    )
    if target_mean is None:
        m_mean_target = Metric(
            "mean_target",
            "Mean tgt",
            _DATA_GAP,
            "data gap",
            "grey",
            mean_target_meaning,
            mean_target_basis,
        )
    else:
        tgt_sub = (
            f"{upside_pct:+.0f}%" if upside_pct is not None else "Street consensus"
        )
        m_mean_target = Metric(
            "mean_target",
            "Mean tgt",
            f"{sym}{target_mean:.0f}",
            tgt_sub,
            "petrol",
            mean_target_meaning,
            mean_target_basis,
        )

    # 4. Dispersion (target_high − target_low; amber when wide ≥ 30% of mean target)
    dispersion_meaning = (
        "Spread between the highest and lowest analyst price targets. "
        "Wide dispersion (≥30% of mean target) signals real disagreement the consensus hides."
    )
    dispersion_basis = (
        "analyst_panel.target_high − target_low; wide = high−low ≥ 30% of mean target"
    )
    if target_high is None or target_low is None:
        m_dispersion = Metric(
            "dispersion",
            "Dispersion",
            _DATA_GAP,
            "data gap",
            "grey",
            dispersion_meaning,
            dispersion_basis,
        )
        is_wide = False
        spread: float | None = None
    else:
        spread = target_high - target_low
        is_wide = (
            target_mean is not None and target_mean > 0 and spread / target_mean >= 0.30
        )
        tone = "amber" if is_wide else "grey"
        sub = "wide" if is_wide else f"{sym}{target_low:.0f}–{sym}{target_high:.0f}"
        m_dispersion = Metric(
            "dispersion",
            "Dispersion",
            f"{sym}{spread:.0f}",
            sub,
            tone,
            dispersion_meaning,
            dispersion_basis,
        )

    # 5. Upside to mean target (honest substitute for unavailable 90-day target history)
    m_upside = _upside_metric(target_mean, current_price)
    if m_upside.value != _DATA_GAP:
        m_upside = Metric(
            m_upside.key,
            "Impl. move",
            m_upside.value,
            "to mean target",
            m_upside.tone,
            m_upside.meaning,
            m_upside.basis,
        )

    # 6. Forward EPS consensus (replaces the unavailable 90-day EPS-estimate history)
    m_fwd_eps = _fwd_eps_metric(getattr(result, "info", {}) or {}, ticker)

    metrics = [
        m_analysts,
        m_consensus,
        m_mean_target,
        m_dispersion,
        m_upside,
        m_fwd_eps,
    ]

    # --- Chips (petrol only — Street rating reported not adopted) ---
    chips = ""

    # POSITIVE chip: always petrol (reports the Street's view, not the model's)
    if mean_rating is not None:
        chips += render_status_chip(
            "POSITIVE",
            f"{mean_rating:.1f}",
            tone="petrol",
            rule=(
                "reports the Street's mean rating (1=most positive … 5=most negative); "
                "third-party; reported not adopted"
            ),
        )

    # TARGETS chip: direction only — dollar value lives in the metric strip (mockup)
    if target_mean is not None:
        chips += render_status_chip(
            "TARGETS",
            "▲",
            tone="petrol",
            rule=(
                "Street consensus mean price target; third-party estimate; "
                "reported not adopted; wide dispersion = real disagreement"
            ),
        )

    reframe_html = _summary_reframe_html(
        count=count,
        mean_rating=mean_rating,
        target_mean=target_mean,
        upside_pct=upside_pct,
        target_low=target_low,
        target_high=target_high,
        is_wide=is_wide,
        ticker=ticker,
    )

    return {
        "metrics": metrics,
        "chips": chips,
        "claim": _claim_headline(mean_rating),
        "reframe": "",
        "reframe_html": reframe_html,
        "verdicts": [
            Verdict("neu", _analyst_context_verdict(count, mean_rating)),
            (
                Verdict(
                    "cau",
                    f"Wide {sym}{target_low:.0f}–{sym}{target_high:.0f} spread = real "
                    "disagreement among analysts — consensus may mask divergence.",
                )
                if is_wide and target_low is not None and target_high is not None
                else Verdict(
                    "neu",
                    "Target spread is within normal range — analyst estimates broadly aligned.",
                )
            ),
        ],
    }


def _price_vs_target_html(result: Any, target_mean: float | None) -> str:
    """Price history (already fetched for the Performance panel) plotted against
    the Street's mean target — a real chart in place of the dead trend slot.
    Not a target *history* (no timestamped estimate series exists); it is an
    honest price/target comparison, so it is labelled accordingly."""
    ph = getattr(result, "price_history", None) or {}
    closes = ph.get("closes") if isinstance(ph, dict) else None
    closes = [float(c) for c in closes] if closes else []
    subh = '<div class="sa-pnl-subh">Price vs. mean target</div>'
    if len(closes) >= 30 and target_mean:
        sym = currency_symbol(currency_for_ticker(getattr(result, "ticker", "")))
        series = [
            ("price", closes, "#0F6E80"),
            ("target", [float(target_mean)] * len(closes), "#9AA5AD"),
        ]
        return (
            subh
            + panel_charts.trend_lines(
                series, x_labels=("start", "now"), label_lines=False
            )
            + '<div class="sa-pnl-cap">Trailing price (teal) vs. today\'s '
            f"{sym}{target_mean:.0f} mean target (grey) — not a 12-mo revision history "
            "(that series is a data gap).</div>"
        )
    return subh + '<div class="sa-pnl-cap">data gap — price history unavailable</div>'


def build_analyst_panel(result: Any) -> str:
    """Compose the full Analyst deep-dive panel HTML (panel #1 in Signals group)."""
    v = build_analyst_view(result)

    # Comparison viz: slop-safe tier labels + mockup purple/grey bars
    rd = getattr(result, "rating_distribution", None) or {}
    rows = _rating_distribution_rows(rd)
    if rows:
        left = (
            '<div class="sa-pnl-subh">Rating distribution</div>'
            + panel_charts.rating_distribution_bars(rows)
            + f'<div class="sa-pnl-cap">{_distribution_skew_caption(rd)}</div>'
        )
    else:
        left = (
            '<div class="sa-pnl-subh">Rating distribution</div>'
            '<div class="sa-pnl-cap">rating distribution unavailable — data gap</div>'
        )

    panel = getattr(result, "analyst_panel", None)
    target_mean = _safe_float(getattr(panel, "target_mean", None))
    right = _price_vs_target_html(result, target_mean)

    return build_panel(
        number=1,
        name="Analyst",
        dot_colour="#5c6bc0",
        info_html=render_info(
            "Street analyst consensus — ratings and price targets reported as third-party context.",
            "analyst_panel.count + mean_rating + target_mean + target_high + target_low",
        ),
        chips_html=v["chips"],
        claim=v["claim"],
        reframe=v.get("reframe", ""),
        reframe_html=v.get("reframe_html"),
        strip_html=_strip_html(v["metrics"]),
        viz_left=left,
        viz_right=right,
        verdicts=v["verdicts"],
        drill="open full analyst — rating history · target revisions · EPS estimate trend",
    )


def _safe_float(val: Any) -> float | None:
    """Return float or None on any missing/unconvertible value."""
    try:
        return float(val) if val is not None else None
    except (TypeError, ValueError):
        return None
