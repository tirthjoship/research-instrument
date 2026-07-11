"""Supply-chain panel (spec D12): structural group position — context, not a signal.

Last of the 4 Signals-group panels (Analyst, Buzz, Sentiment, Supply chain) —
10th and final deep-dive panel of the Stock Analysis tab overall.

Supply-chain grouping tells you which tickers share sector exposure and move
together historically.  High co-movement means sector risk travels together.
This is structural context only — it is NOT a directional signal.

The group itself is resolved dynamically per ticker
(``supply_chain_resolver.resolve_supply_chain_group``) — the best-fit group by
measured co-movement across every YAML/sector candidate the ticker belongs to,
not the first YAML match. See ADR-027.

Wired: Co-movement, 1-day member moves, Group 1w / ticker-vs-group excess (from
``member_closes``), a group bubble map, and a ticker-vs-group 14-day trend line.

DATA-GAP items:
- Lead/lag quantile (not computed — no lead-series pipeline wired; dropped from
  the metric strip per the mockup, which replaced it with Group 1w / vs-group)
"""

from __future__ import annotations

import html as _html
from typing import Any

from adapters.visualization.analysis.scoring.supply_chain import one_week_return_pct
from adapters.visualization.components import panel_charts
from adapters.visualization.components.info_tip import render_info
from adapters.visualization.components.status_chip import render_status_chip
from adapters.visualization.tabs.stock_analysis.panel import Verdict, build_panel
from adapters.visualization.tabs.stock_analysis.valuation_view import Metric

# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

_DATA_GAP = "—"
_HIGH_COMOVEMENT = 0.6
_TREND_DAYS = 14

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


def _group_provenance_word(provenance: str | None) -> str:
    if provenance == "yaml+correlation":
        return "mapped"
    if provenance == "correlation_only":
        return "corr-cluster"
    return "data gap"


def _ticker_vs_group_series(
    closes_by_ticker: dict[str, list[float]],
    ticker: str,
    peers: list[str],
    days: int = _TREND_DAYS,
) -> tuple[list[float], list[float]] | None:
    """(ticker_pct_series, group_avg_pct_series) over the last ``days`` closes,
    both normalized to 0% at the start of the window. ``None`` if there isn't
    enough aligned history for the ticker plus at least one peer.
    """
    usable = {t: closes for t, closes in closes_by_ticker.items() if len(closes) >= 2}
    if ticker not in usable:
        return None
    peer_series = [t for t in peers if t in usable]
    if not peer_series:
        return None

    n = min(days, min(len(usable[t]) for t in [ticker, *peer_series]))
    if n < 2:
        return None

    def pct_series(closes: list[float]) -> list[float]:
        tail = closes[-n:]
        base = tail[0]
        if base == 0:
            return []
        return [(c - base) / base * 100.0 for c in tail]

    ticker_series = pct_series(usable[ticker])
    peer_pct = [pct_series(usable[t]) for t in peer_series]
    peer_pct = [p for p in peer_pct if p]
    if not ticker_series or not peer_pct:
        return None
    group_series = [sum(p[i] for p in peer_pct) / len(peer_pct) for i in range(n)]
    return ticker_series, group_series


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def build_supply_chain_view(result: Any) -> dict[str, Any]:
    """Build the supply-chain view-model.

    Returns a dict with keys: metrics, chips, claim, reframe, verdicts.

    Six metrics (mirrors the mockup — no separate lag/lead-lag tiles):
      1. Group        — resolved group display name + provenance (mapped/corr-cluster)
      2. Role         — leader or follower (from _is_leader flag)
      3. Members      — total tickers in group (leaders + followers)
      4. Group 1w     — average 1-week return across the other group members
      5. {ticker} vs grp — ticker's own 1-week return minus the group average
      6. Co-movement  — average pairwise correlation, or DATA-GAP if not computed

    Chips:
      LEADER · {group_display} (petrol) / MEMBER · {group_display} (grey)
      co-move {value} (grey) — only when co-movement is computed
      DATA-GAP chip when supply_chain_group is None
    """
    grp: dict[str, Any] | None = getattr(result, "supply_chain_group", None)
    ticker = str(getattr(result, "ticker", "") or "TICKER")

    has_data = grp is not None

    if grp is not None:
        group_display: str = str(
            grp.get("group_display") or grp.get("group", _DATA_GAP)
        )
        provenance: str | None = grp.get("provenance")
        is_leader: bool = bool(grp.get("_is_leader", False))
        leaders: list[Any] = list(grp.get("leaders", []) or [])
        followers: list[Any] = list(grp.get("followers", []) or [])
    else:
        group_display = _DATA_GAP
        provenance = None
        is_leader = False
        leaders = []
        followers = []

    role_str = "Leader" if is_leader else "Follower"
    member_count = len(leaders) + len(followers)
    co_movement: float | None = grp.get("co_movement") if grp is not None else None
    group_1w: float | None = grp.get("group_1w_pct") if grp is not None else None
    vs_group: float | None = grp.get("vs_group_1w_pct") if grp is not None else None

    # ---- 6 metrics ----
    metrics: list[Metric] = []

    # 1. Group
    metrics.append(
        Metric(
            "sc_group",
            "Group",
            group_display,
            _group_provenance_word(provenance) if has_data else "data gap",
            "petrol" if is_leader else "grey",
            "The value-chain group this ticker is mapped to — resolved dynamically "
            "by measured co-movement, not a fixed first-match lookup.",
            "supply_chain_group.group_display (provenance: yaml+correlation | correlation_only)",
        )
    )

    # 2. Role
    metrics.append(
        Metric(
            "sc_role",
            "Role",
            role_str if has_data else _DATA_GAP,
            ("central" if is_leader else "trails leaders") if has_data else "data gap",
            "petrol" if is_leader else "grey",
            (
                "Structural role within the group: highest market cap, most "
                "correlated to the rest of the cluster, or a curated YAML leader. "
                "Descriptive, not a directional ranking."
            ),
            "supply_chain_group._is_leader → leader | follower",
        )
    )

    # 3. Members
    metrics.append(
        Metric(
            "sc_members",
            "Members",
            str(member_count) if has_data else _DATA_GAP,
            "names" if has_data else "data gap",
            "grey",
            "Total number of tickers in this resolved group (leaders + followers).",
            "len(supply_chain_group.leaders) + len(supply_chain_group.followers)",
        )
    )

    # 4. Group 1w — average 1-week return across the other members
    metrics.append(
        Metric(
            "sc_group1w",
            "Group 1w",
            f"{group_1w:+.0f}%" if group_1w is not None else _DATA_GAP,
            "avg" if group_1w is not None else "data gap",
            "grey",
            "Average 1-week return across the group's other members.",
            "avg(one_week_return_pct(member closes))",
        )
    )

    # 5. {ticker} vs grp — ticker's 1-week excess over the group average
    metrics.append(
        Metric(
            "sc_vsgroup",
            f"{ticker} vs grp",
            f"{vs_group:+.0f}pts" if vs_group is not None else _DATA_GAP,
            (
                ("ahead" if vs_group >= 0 else "behind")
                if vs_group is not None
                else "data gap"
            ),
            "amber" if vs_group is not None and vs_group >= 0 else "grey",
            f"{ticker}'s own 1-week return minus the group's average 1-week return.",
            "ticker_1w_return - group_1w_avg_return",
        )
    )

    # 6. Co-movement — average pairwise correlation of daily returns, or DATA-GAP
    metrics.append(
        Metric(
            "sc_comovement",
            "Co-move",
            f"{co_movement:.2f}" if co_movement is not None else _DATA_GAP,
            (
                ("tight" if co_movement >= _HIGH_COMOVEMENT else "loose")
                if co_movement is not None
                else "data gap — insufficient price history"
            ),
            (
                "amber"
                if co_movement is not None and co_movement >= _HIGH_COMOVEMENT
                else "grey"
            ),
            (
                "Average pairwise correlation of daily returns across the group "
                "(~3mo). High = the group trades as a pack — sector risk travels "
                "together, not a directional signal."
            ),
            "avg(pearson(daily returns)) across supply_chain_group members",
        )
    )

    # ---- Chips ----
    if has_data:
        chip_lbl = "LEADER" if is_leader else "MEMBER"
        chip_tone = "petrol" if is_leader else "grey"
        chip_rule = (
            "structural position in the dynamically-resolved group; "
            "leader = highest market cap, most central, or curated YAML leader; "
            "descriptive only — not a directional ranking"
        )
        chips = render_status_chip(
            chip_lbl,
            group_display,
            tone=chip_tone,
            rule=chip_rule,
        )
        if co_movement is not None:
            chips += render_status_chip(
                "co-move",
                f"{co_movement:.2f}",
                tone="grey",
                rule="average pairwise correlation of daily returns across the "
                "resolved group; descriptive, not a directional signal",
            )
    else:
        chips = render_status_chip(
            "DATA-GAP",
            "no group",
            tone="grey",
            rule="supply_chain_group is None — no candidate group cleared the "
            "minimum member count / co-movement threshold for this ticker",
        )

    if co_movement is not None:
        comovement_verdict = (
            Verdict(
                "cau",
                f"Co-movement {co_movement:.2f} across the group — high, sector risk travels together.",
            )
            if co_movement >= _HIGH_COMOVEMENT
            else Verdict(
                "neu",
                f"Co-movement {co_movement:.2f} across the group — moderate, some independent movement.",
            )
        )
        comovement_reframe = (
            f"Co-movement {co_movement:.2f} — high means sector risk travels together; "
            "structural context, not a signal."
        )
    else:
        comovement_verdict = Verdict(
            "neu",
            "Co-movement correlation not wired — data gap, insufficient price history.",
        )
        comovement_reframe = (
            "High co-movement means sector risk travels together; "
            "structural context, not a signal. "
            "Co-movement correlation not wired — data gap."
        )

    if is_leader and co_movement is not None and co_movement >= _HIGH_COMOVEMENT:
        claim = "The anchor of its group — peers move around it"
        reframe = (
            f"{ticker} is the largest/most-central name in the {group_display} group "
            f"({member_count} names), which trades tightly together (co-move "
            f"{co_movement:.2f}). Useful for understanding what moves with the group "
            "— not a forward-looking claim."
        )
    else:
        claim = "Structural supply-chain position — group membership and co-movement context."
        reframe = (
            f"{comovement_reframe} "
            "1-day price moves and 1-week group comparison are wired from live quotes."
        )

    return {
        "metrics": metrics,
        "chips": chips,
        "claim": claim,
        "reframe": reframe,
        "verdicts": [
            comovement_verdict,
            Verdict(
                "cau",
                "High co-movement = group/sector risk travels together — structural context, not a signal.",
            ),
        ],
    }


def build_supply_chain_panel(result: Any) -> str:
    """Compose the full Supply-chain deep-dive panel HTML (4th of the Signals-group panels)."""
    v = build_supply_chain_view(result)
    grp: dict[str, Any] | None = getattr(result, "supply_chain_group", None)
    ticker = str(getattr(result, "ticker", "") or "")

    # Left viz: group bubble map (market cap x-position/size, 1-week move y-position)
    if grp is not None:
        leaders: list[str] = [str(t) for t in (grp.get("leaders") or [])]
        followers: list[str] = [str(t) for t in (grp.get("followers") or [])]
        all_tickers = leaders + followers
        market_caps: dict[str, Any] = grp.get("member_market_caps") or {}
        member_closes: dict[str, list[float]] = grp.get("member_closes") or {}
        this_cap = float(getattr(result, "market_cap", 0.0) or 0.0)

        bubble_rows: list[tuple[str, float, float, bool]] = []
        for t in all_tickers:
            cap = float(market_caps.get(t, 0.0) or 0.0)
            if t == ticker and cap <= 0:
                cap = this_cap
            week_move = one_week_return_pct(member_closes.get(t, [])) or 0.0
            if cap > 0:
                bubble_rows.append((t, cap, week_move, t == ticker))

        bubbles_html = panel_charts.group_bubbles(bubble_rows)
        left = '<div class="sa-pnl-subh">The group, this week</div>' + (
            bubbles_html
            or '<div class="sa-pnl-cap">member market caps unavailable — data gap</div>'
        )
    else:
        left = (
            '<div class="sa-pnl-subh">The group, this week</div>'
            '<div class="sa-pnl-cap">no supply-chain group assigned — data gap</div>'
        )

    # Right viz: ticker-vs-group 14-day trend
    right = f'<div class="sa-pnl-subh">{_html.escape(ticker)} vs group, {_TREND_DAYS} days</div>'
    series = None
    if grp is not None:
        member_closes = grp.get("member_closes") or {}
        peers = [
            str(t)
            for t in (grp.get("leaders") or []) + (grp.get("followers") or [])
            if t != ticker
        ]
        if member_closes:
            series = _ticker_vs_group_series(member_closes, ticker, peers)
    if series is not None:
        ticker_series, group_series = series
        chart = panel_charts.trend_lines(
            [(ticker, ticker_series, "#0F6E80"), ("group", group_series, "#9aa6aa")],
            unit="%",
            label_lines=False,
        )
        right += chart
        right += (
            f'<div class="sa-pnl-cap">{_html.escape(ticker)} (petrol) vs the group '
            "average (grey), normalized to 0% at the start of the window.</div>"
        )
    else:
        right += (
            '<div class="sa-pnl-cap">ticker-vs-group trend unavailable — data gap '
            "(insufficient aligned price history)</div>"
        )

    return build_panel(
        number=4,
        name="Supply chain",
        dot_colour="#2aa198",
        info_html=render_info(
            "Structural supply-chain position: resolved group membership, role, "
            "co-movement, and 1-week performance vs the group.",
            "supply_chain_group.{group_display,leaders,followers,co_movement,_is_leader}",
        ),
        chips_html=v["chips"],
        claim=v["claim"],
        reframe=v["reframe"],
        strip_html=_strip_html(v["metrics"]),
        viz_left=left,
        viz_right=right,
        verdicts=v["verdicts"],
        drill="open full supply-chain — full member table · supplier↔customer map · rolling co-movement",
    )
