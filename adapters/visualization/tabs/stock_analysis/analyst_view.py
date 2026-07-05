"""Analyst panel (spec D12): context-only — reports the Street's mean rating and targets.

This panel reports third-party analyst ratings and price targets as facts.
It does NOT adopt, endorse, or echo analyst recommendations as the project's view.
All tone is petrol (never green): the data is attributed to the Street, not the model.

DATA-GAP items: mean-target trend (no time series wired). The 90-day target and
EPS-estimate history are unavailable, so those slots show the current implied
upside to the mean target and the consensus forward EPS instead.
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

_STRIP_TILE = (
    '<div class="sa-tile t-{tone}"><div class="lab">{lbl} {info}</div>'
    '<div class="num">{value}</div><div class="sub">{sub}</div></div>'
)

_DATA_GAP = "—"


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


def _fwd_eps_metric(info: dict[str, Any]) -> Metric:
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
    return Metric(
        "fwd_eps", "Fwd EPS", f"${eps:.2f}", "consensus est", "petrol", meaning, basis
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
        "contributing" if count else "data gap",
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
            "Street mean (1=best)",
            "petrol",
            consensus_meaning,
            consensus_basis,
        )

    # 3. Mean target
    mean_target_meaning = "Analyst consensus mean price target in USD."
    mean_target_basis = (
        "analyst_panel.target_mean; Street price target; third-party, not adopted"
    )
    if target_mean is None:
        m_mean_target = Metric(
            "mean_target",
            "Mean target",
            _DATA_GAP,
            "data gap",
            "grey",
            mean_target_meaning,
            mean_target_basis,
        )
    else:
        m_mean_target = Metric(
            "mean_target",
            "Mean target",
            f"${target_mean:.0f}",
            "Street consensus",
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
        range_str = f"${target_low:.0f}–${target_high:.0f}"
        sub = f"wide {range_str}" if is_wide else range_str
        m_dispersion = Metric(
            "dispersion",
            "Dispersion",
            f"${spread:.0f}",
            sub,
            tone,
            dispersion_meaning,
            dispersion_basis,
        )

    # 5. Upside to mean target (replaces the unavailable 90-day target history)
    m_upside = _upside_metric(
        target_mean, _safe_float(getattr(result, "current_price", None))
    )

    # 6. Forward EPS consensus (replaces the unavailable 90-day EPS-estimate history)
    m_fwd_eps = _fwd_eps_metric(getattr(result, "info", {}) or {})

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

    # TARGETS chip: petrol — target direction is the Street's view
    if target_mean is not None:
        chips += render_status_chip(
            "TARGETS ▲",
            f"${target_mean:.0f}",
            tone="petrol",
            rule=(
                "Street consensus mean price target; third-party estimate; "
                "reported not adopted; wide dispersion = real disagreement"
            ),
        )

    return {
        "metrics": metrics,
        "chips": chips,
        "claim": "Street analyst consensus — ratings and targets reported as third-party context.",
        "reframe": (
            "Wide dispersion = real disagreement the consensus hides. "
            "Upside is implied by the Street's mean target; forward EPS is a consensus "
            "estimate. All figures are the Street's view; this panel never adopts them."
        ),
        "verdicts": [
            Verdict(
                "neu",
                "Rating distribution shown when available; mean-target trend needs a history (data gap).",
            ),
            (
                Verdict(
                    "cau",
                    f"Wide ${target_low:.0f}–${target_high:.0f} spread = real disagreement "
                    "among analysts — consensus may mask divergence.",
                )
                if is_wide and target_low is not None and target_high is not None
                else Verdict(
                    "neu",
                    "Target spread is within normal range — analyst estimates broadly aligned.",
                )
            ),
        ],
    }


def build_analyst_panel(result: Any) -> str:
    """Compose the full Analyst deep-dive panel HTML (panel #1 in Signals group)."""
    v = build_analyst_view(result)

    # Comparison viz: rating distribution as numeric tiers 1..5 (slop-safe labels)
    rd = getattr(result, "rating_distribution", None) or {}
    total = sum(int(x or 0) for x in rd.values()) if rd else 0
    if total > 0:
        rows = [(str(i), float(rd.get(f"r{i}", 0) or 0), False) for i in range(1, 6)]
        left = (
            '<div class="sa-pnl-subh">Rating distribution</div>'
            + panel_charts.peer_bars(rows, unit="")
            + '<div class="sa-pnl-cap">analyst tiers 1 (most positive) → 5 (most negative)</div>'
        )
    else:
        left = (
            '<div class="sa-pnl-subh">Rating distribution</div>'
            '<div class="sa-pnl-cap">rating distribution unavailable — data gap</div>'
        )

    # Trend viz: mean-target trend — DATA-GAP (no time series wired)
    right = (
        '<div class="sa-pnl-subh">Mean-target trend</div>'
        '<div class="sa-pnl-cap">mean-target trend not wired — data gap</div>'
    )

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
        reframe=v["reframe"],
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
