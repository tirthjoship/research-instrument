"""Supply-chain panel (spec D12): structural group position — context, not a signal.

Supply-chain grouping tells you which tickers share sector exposure and move
together historically.  High co-movement means sector risk travels together.
This is structural context only — it is NOT a directional signal.

Wired: Co-movement (average pairwise correlation of daily returns across the
group, from ``supply_chain_group.co_movement``) and 1-day price moves for
group members (``supply_chain_group.member_moves``).

DATA-GAP items:
- Lead/lag quantile (not computed — no lead-series pipeline wired)
- Ticker-vs-group lead series (no time-series wired)
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
_HIGH_COMOVEMENT = 0.6

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


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def build_supply_chain_view(result: Any) -> dict[str, Any]:
    """Build the supply-chain view-model.

    Returns a dict with keys: metrics, chips, claim, reframe, verdicts.

    Six metrics:
      1. Group       — supply-chain group name
      2. Role        — leader or follower (from _is_leader flag)
      3. Members     — total tickers in group (leaders + followers)
      4. Typical lag — characteristic lag in days from group config
      5. Co-movement — average pairwise correlation, or DATA-GAP if not computed
      6. Lead/lag    — DATA-GAP (quantile series not wired)

    Chips:
      LEADER · {group} (petrol) when _is_leader is True
      MEMBER · {group} (grey)   when _is_leader is False
      DATA-GAP chip              when supply_chain_group is None
    """
    grp: dict[str, Any] | None = getattr(result, "supply_chain_group", None)

    has_data = grp is not None

    if grp is not None:
        group_name: str = str(grp["group"])
        is_leader: bool = bool(grp.get("_is_leader", False))
        leaders: list[Any] = list(grp.get("leaders", []) or [])
        followers: list[Any] = list(grp.get("followers", []) or [])
        lag_days: int | None = grp.get("typical_lag_days")
    else:
        group_name = _DATA_GAP
        is_leader = False
        leaders = []
        followers = []
        lag_days = None

    role_str = "leader" if is_leader else "follower"
    member_count = len(leaders) + len(followers)
    lag_str = f"{lag_days} days" if lag_days is not None else _DATA_GAP
    co_movement: float | None = grp.get("co_movement") if grp is not None else None

    # ---- 6 metrics ----
    metrics: list[Metric] = []

    # 1. Group
    metrics.append(
        Metric(
            "sc_group",
            "Group",
            group_name,
            "supply-chain cluster" if has_data else "data gap",
            "grey",
            "Supply-chain cluster this ticker belongs to, from the market config.",
            "supply_chain_group.group",
        )
    )

    # 2. Role
    metrics.append(
        Metric(
            "sc_role",
            "Role",
            role_str if has_data else _DATA_GAP,
            "structural position" if has_data else "data gap",
            "grey",
            (
                "Structural role within the supply-chain group: 'leader' tickers historically "
                "move before 'follower' tickers.  This is a config-time designation, not a "
                "dynamically measured ranking."
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
            "tickers in group" if has_data else "data gap",
            "grey",
            "Total number of tickers in this supply-chain group (leaders + followers).",
            "len(supply_chain_group.leaders) + len(supply_chain_group.followers)",
        )
    )

    # 4. Typical lag
    metrics.append(
        Metric(
            "sc_lag",
            "Typical lag",
            lag_str if has_data else _DATA_GAP,
            "characteristic delay" if has_data else "data gap",
            "grey",
            (
                "Characteristic number of trading days by which follower tickers "
                "historically lag leader moves within this group.  From market config — "
                "not dynamically measured."
            ),
            "supply_chain_group.typical_lag_days",
        )
    )

    # 5. Co-movement — average pairwise correlation of daily returns, or DATA-GAP
    metrics.append(
        Metric(
            "sc_comovement",
            "Co-movement",
            f"{co_movement:.2f}" if co_movement is not None else _DATA_GAP,
            (
                "pairwise correlation"
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

    # 6. Lead/lag — DATA-GAP
    metrics.append(
        Metric(
            "sc_lead_lag",
            "Lead/lag",
            _DATA_GAP,
            "data gap",
            "grey",
            (
                "Quantile of lead/lag timing relative to the group.  "
                "The lead-series computation is not wired — this value is always data gap."
            ),
            "data gap — lead/lag quantile series not wired",
        )
    )

    # ---- Chips ----
    if has_data:
        chip_lbl = "LEADER" if is_leader else "MEMBER"
        chip_tone = "petrol" if is_leader else "grey"
        chip_rule = (
            "structural position from the supply-chain config; "
            "leader tickers historically move before followers in this group; "
            "descriptive only — not a directional ranking"
        )
        chips = render_status_chip(
            chip_lbl,
            group_name,
            tone=chip_tone,
            rule=chip_rule,
        )
    else:
        chips = render_status_chip(
            "DATA-GAP",
            "no group",
            tone="grey",
            rule="supply_chain_group is None — no group assignment available for this ticker",
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

    return {
        "metrics": metrics,
        "chips": chips,
        "claim": "Structural supply-chain position — group membership and characteristic lag.",
        "reframe": (
            f"{comovement_reframe} "
            "Lead/lag quantile is not wired — data gap. "
            "1-day price moves for group members are wired from live quotes."
        ),
        "verdicts": [
            comovement_verdict,
            Verdict(
                "neu",
                "Lead/lag series not wired — data gap, quantile computation absent.",
            ),
        ],
    }


def build_supply_chain_panel(result: Any) -> str:
    """Compose the full Supply-chain deep-dive panel HTML (panel #4 in Signals group)."""
    v = build_supply_chain_view(result)
    grp: dict[str, Any] | None = getattr(result, "supply_chain_group", None)

    # Comparison viz: group members as equal-weight peer bars
    if grp is not None:
        pnl_leaders: list[str] = [str(t) for t in (grp.get("leaders") or [])]
        pnl_followers: list[str] = [str(t) for t in (grp.get("followers") or [])]
        all_tickers = pnl_leaders + pnl_followers
        moves: dict[str, Any] = grp.get("member_moves") or {}
        subject = str(getattr(result, "ticker", "") or "")
        rows: list[tuple[str, float, bool]] = [
            (t, float(moves.get(t, 0.0) or 0.0), t == subject) for t in all_tickers
        ]
        bars_html = panel_charts.peer_bars(rows, unit="%")
        cap = (
            "1-day price move per member"
            if moves
            else "member moves unavailable — data gap"
        )
        left = (
            '<div class="sa-pnl-subh">Group members</div>'
            + bars_html
            + f'<div class="sa-pnl-cap">{cap}</div>'
        )
    else:
        left = (
            '<div class="sa-pnl-subh">Group members</div>'
            '<div class="sa-pnl-cap">no supply-chain group assigned — data gap</div>'
        )

    # Trend viz: ticker-vs-group lead series — DATA-GAP
    right = (
        '<div class="sa-pnl-subh">Lead series</div>'
        '<div class="sa-pnl-cap">ticker-vs-group lead series not wired — data gap</div>'
    )

    return build_panel(
        number=4,
        name="Supply chain",
        dot_colour="#2aa198",
        info_html=render_info(
            "Structural supply-chain position: group membership, typical lag, co-movement context.",
            "supply_chain_group.{group,leaders,followers,typical_lag_days,_is_leader}",
        ),
        chips_html=v["chips"],
        claim=v["claim"],
        reframe=v["reframe"],
        strip_html=_strip_html(v["metrics"]),
        viz_left=left,
        viz_right=right,
        verdicts=v["verdicts"],
        drill="open full supply-chain — group timeline · co-movement matrix · lag distribution",
    )
