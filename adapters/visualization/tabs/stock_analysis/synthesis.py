"""Story-this-week synthesis (spec D2): descriptive prose + 5 jump-link claim chips."""

from __future__ import annotations

import html as _html
from dataclasses import dataclass
from typing import Any

from adapters.visualization.components.info_tip import render_info


@dataclass(frozen=True)
class ClaimChip:
    label: str
    value: str
    tone: str
    meaning: str
    basis: str
    anchor: str


@dataclass(frozen=True)
class SynthesisView:
    prose: str
    chips: tuple[ClaimChip, ...]


def _valuation_chip(result: Any) -> ClaimChip:
    pct = (getattr(result, "peer_percentiles", {}) or {}).get("P/E")
    if pct is None:
        return ClaimChip(
            "Valuation",
            "data gap",
            "grey",
            "No peer P/E percentile available.",
            "peer_percentiles",
            "sa-fundamentals",
        )
    pct_i = int(round(float(pct)))
    if pct_i >= 75:
        tone, tail = "amber", "rich"
    elif pct_i <= 25:
        tone, tail = "amber", "cheap vs peers"
    else:
        tone, tail = "grey", "typical"
    return ClaimChip(
        "Valuation",
        f"{pct_i}th · {tail}",
        tone,
        f"P/E sits at the {pct_i}th percentile of peers — describes price level only, not over/undervalued.",
        "peer_percentiles",
        "sa-fundamentals",
    )


def _growth_chip(result: Any) -> ClaimChip:
    g = (getattr(result, "info", {}) or {}).get("revenueGrowth")
    if g is None:
        return ClaimChip(
            "Growth",
            "data gap",
            "grey",
            "No revenue-growth figure available.",
            "info.revenueGrowth",
            "sa-fundamentals",
        )
    pctg = round(float(g) * 100)
    tone = "green" if pctg > 0 else "grey"
    return ClaimChip(
        "Growth",
        f"{pctg:+d}% rev",
        tone,
        f"Revenue {pctg:+d}% year over year — a trailing fact, not a projection.",
        "info.revenueGrowth",
        "sa-fundamentals",
    )


def _analyst_chip(result: Any) -> ClaimChip:
    panel = getattr(result, "analyst_panel", None)
    rating = getattr(panel, "mean_rating", None) if panel else None
    if rating is None or getattr(panel, "data_gap", False):
        return ClaimChip(
            "Analysts",
            "data gap",
            "grey",
            "No analyst consensus available.",
            "analyst_panel",
            "sa-signals",
        )
    # report the Street, never endorse -> petrol/grey, never green
    r = float(rating)
    tone_word = "positive" if r <= 2.0 else "neutral" if r <= 3.0 else "negative"
    return ClaimChip(
        "Analysts",
        f"{tone_word} · {r:.1f}",
        "petrol",
        f"Mean rating {r:.1f} on 1-5 (1=most positive). Third-party; reported, not adopted.",
        "analyst_panel",
        "sa-signals",
    )


def _insider_chip(result: Any) -> ClaimChip:
    txns = getattr(result, "insider_transactions", []) or []
    net = sum(float(t.get("value", 0) or 0) for t in txns)
    if not txns:
        return ClaimChip(
            "Insiders",
            "data gap",
            "grey",
            "No insider transactions disclosed.",
            "insider_transactions",
            "sa-market",
        )
    # spec D11 + anti-false-claim: insider signal is FALSIFIED — grey (descriptive), never coloured as bad
    tone = "grey"
    direction = "▼ net reducing" if net < 0 else "▲ net accumulating"
    return ClaimChip(
        "Insiders",
        direction,
        tone,
        "Net Form-4 activity last quarter. Disclosed fact; insider-cluster signal falsified — never read as a trade call.",
        "insider_transactions · signal falsified",
        "sa-market",
    )


def _buzz_chip(result: Any) -> ClaimChip:
    buzz = getattr(result, "buzz_signals", []) or []
    if not buzz:
        return ClaimChip(
            "Buzz",
            "data gap",
            "grey",
            "No buzz signals available.",
            "buzz_signals",
            "sa-signals",
        )
    n = len(buzz)
    return ClaimChip(
        "Buzz",
        f"+ {n} sources",
        "grey",
        "Attention across sources. Buzz to return falsified (ADR-044); context only, never a signal.",
        "buzz_signals · ADR-044",
        "sa-signals",
    )


def build_synthesis_view(result: Any) -> SynthesisView:
    chips = (
        _valuation_chip(result),
        _growth_chip(result),
        _analyst_chip(result),
        _insider_chip(result),
        _buzz_chip(result),
    )
    val = chips[0].value
    gro = chips[1].value
    prose = (
        f"Valuation reads <b>{val}</b> on revenue growth of <b>{gro}</b>; "
        "the Street's view and insider activity appear below as disclosed facts — context, not a forecast."
    )
    return SynthesisView(prose=prose, chips=chips)


def _chip_html(c: ClaimChip) -> str:
    e = _html.escape
    info = render_info(c.meaning, c.basis)
    return (
        f'<a class="sa-cchip t-{c.tone}" href="#{e(c.anchor)}">'
        f"{e(c.label)} <b>{e(c.value)}</b>{info}</a>"
    )


def build_synthesis_html(view: SynthesisView) -> str:
    chips = "".join(_chip_html(c) for c in view.chips)
    return (
        '<div class="sa-eyebrow">Story this week &nbsp;·&nbsp; '
        '<span class="sa-tagmono">DESCRIPTIVE · NOT A FORECAST</span></div>'
        f'<div class="sa-prose">{view.prose}</div>'
        f'<div class="sa-chips">{chips}</div>'
    )
