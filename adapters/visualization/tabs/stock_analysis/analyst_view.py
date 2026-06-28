"""Analyst panel (spec D12): context-only — reports the Street's mean rating and targets.

This panel reports third-party analyst ratings and price targets as facts.
It does NOT adopt, endorse, or echo analyst recommendations as the project's view.
All tone is petrol (never green): the data is attributed to the Street, not the model.

DATA-GAP items: rating distribution (no breakdown wired), target 90 days ago
(no historical series), EPS estimate 90 days ago (no EPS-estimate history wired),
mean-target trend (no time series wired).
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
      5. Target 90d ago (DATA-GAP — no historical series wired)
      6. EPS est 90d (DATA-GAP — no EPS-estimate history wired)

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
                "target_90d",
                "Target 90d",
                _DATA_GAP,
                "data gap",
                "grey",
                "Analyst mean price target from 90 days ago; requires historical series not wired.",
                "data gap — historical target series not wired",
            ),
            Metric(
                "eps_est_90d",
                "EPS est 90d",
                _DATA_GAP,
                "data gap",
                "grey",
                "EPS consensus estimate from 90 days ago; requires EPS-estimate history not wired.",
                "data gap — EPS estimate history not wired",
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
        sub = "wide disagreement" if is_wide else "spread"
        m_dispersion = Metric(
            "dispersion",
            "Dispersion",
            f"${spread:.0f}",
            sub,
            tone,
            dispersion_meaning,
            dispersion_basis,
        )

    # 5. Target 90d ago — DATA-GAP
    m_target_90d = Metric(
        "target_90d",
        "Target 90d",
        _DATA_GAP,
        "data gap",
        "grey",
        "Analyst mean price target from 90 days ago; requires historical series not wired.",
        "data gap — historical target series not wired",
    )

    # 6. EPS est 90d — DATA-GAP
    m_eps_est_90d = Metric(
        "eps_est_90d",
        "EPS est 90d",
        _DATA_GAP,
        "data gap",
        "grey",
        "EPS consensus estimate from 90 days ago; requires EPS-estimate history not wired.",
        "data gap — EPS estimate history not wired",
    )

    metrics = [
        m_analysts,
        m_consensus,
        m_mean_target,
        m_dispersion,
        m_target_90d,
        m_eps_est_90d,
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
            "Target 90d and EPS est 90d are not wired (data gap — no historical series). "
            "All ratings are the Street's view; this panel never adopts them."
        ),
        "verdicts": [
            Verdict(
                "neu",
                "Rating distribution shown when available; mean-target trend needs a history (data gap).",
            ),
            (
                Verdict(
                    "cau",
                    "Wide dispersion signals genuine disagreement among analysts — consensus may mask divergence.",
                )
                if is_wide
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
