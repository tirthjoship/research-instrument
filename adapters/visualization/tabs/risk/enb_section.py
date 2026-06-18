"""Effective number of bets section."""

from __future__ import annotations

import html as _html
from typing import Any

from adapters.visualization.components.tooltip import tooltip

from ._theme import *  # noqa: F403, F405


def _enb_section(macro: dict[str, Any]) -> str:
    """ENB block + expandable drill-down: named bets + how-to-raise."""
    enb = macro.get("enb")
    pc_variance: list[float] = macro.get("pc_variance") or []
    pc_labels: list[str] = macro.get("pc_labels") or []
    pc_gap: bool = bool(macro.get("pc_labels_data_gap", False))
    total_h = macro.get("total_holdings", "?")
    sector_gaps: list[str] = macro.get("sector_gaps") or []

    if enb is None:
        return (
            '<div class="ri-sec">How many real bets?</div>'
            '<div class="risk-enb">'
            '<p style="font-size:12.5px;color:#33474c">DATA-GAP: effective bets not available &#8212; '
            "run weekly-brief to populate.</p>"
            "</div>"
        )

    # Degenerate-covariance guard: enb may be 0.0 with no pc_variance when the
    # portfolio has too few history points for a meaningful decomposition.
    # Treat this the same as the data-gap case rather than crashing on pc_variance[0].
    if not pc_variance:
        return (
            f'<div class="ri-sec">How many real bets? {tooltip("Effective bets")}</div>'
            '<div class="risk-enb">'
            f'<div class="risk-enbnum">'
            f'<div class="risk-big-n">{enb:.1f}</div>'
            f'<div class="risk-of">of {total_h} names</div>'
            '<div class="risk-lab">Effective bets</div>'
            "</div>"
            '<div class="risk-enbright">'
            f'<p style="font-size:12.5px;color:#33474c">DATA-GAP: not enough price history to '
            "decompose bets &#8212; run weekly-brief once more history is available. "
            "The effective-bets count is shown but variance attribution requires more data.</p>"
            "</div></div>"
        )

    # Build PC variance bars (top 3 + residual).
    # The use case truncates pc_variance to the top-3 eigenvalue shares, so we
    # compute the residual as the variance NOT captured by the shown components
    # rather than summing the (always-empty) tail pc_variance[3:].
    top3 = (
        list(zip(pc_variance[:3], pc_labels[:3])) if pc_variance and pc_labels else []
    )
    rest_variance = max(0.0, 1.0 - sum(pc_variance))
    max_pc = max(pc_variance[:3]) if pc_variance else 1.0

    pc_rows = ""
    for i, (var, lbl) in enumerate(top3):
        pct_of_max = var / max_pc * 100.0 if max_pc > 0 else 0.0
        row_name = f"PC-{i+1}"
        fill_class = "risk-pf one" if i == 0 else "risk-pf"
        pc_rows += (
            f'<div class="risk-pcrow">'
            f'<span class="risk-pn">{row_name}</span>'
            f'<span class="risk-pt"><span class="{fill_class}" style="width:{pct_of_max:.0f}%"></span></span>'
            f'<span class="risk-pv">{var:.0%}</span>'
            "</div>"
        )
    if rest_variance > 0:
        pc_rows += (
            '<div class="risk-pcrow">'
            f'<span class="risk-pn">PC 4&#8211;{total_h}</span>'
            f'<span class="risk-pt"><span class="risk-pf" style="width:{rest_variance/max_pc*100:.0f}%;background:#cdd6d6"></span></span>'
            f'<span class="risk-pv">{rest_variance:.0%}</span>'
            "</div>"
        )

    # Build the expandable drill-down
    # Bet names: use labels if not data-gap, else "Bet N"
    def _bet_name(i: int) -> str:
        if pc_gap or i >= len(pc_labels):
            return f"Bet {i+1}"
        return _html.escape(pc_labels[i])

    def _bet_desc(i: int) -> str:
        if pc_gap:
            return ""
        if i == 0:
            return (
                "Your book's largest shared axis. The names loading on it move "
                "together; swapping one for another <i>within</i> this axis does "
                "NOT reduce the bet."
            )
        if i == 1:
            return "A secondary axis &#8212; a genuinely different, smaller source of risk from the dominant one."
        return "A thin idiosyncratic spread &#8212; the only place your stock-picking actually shows up."

    chaps = ""
    for i in range(min(3, len(pc_variance) if pc_variance else 3)):
        var_pct = f"{pc_variance[i]:.0%}" if i < len(pc_variance) else "?"
        name = _bet_name(i)
        desc = _bet_desc(i)
        cnum_color = f'style="color:{_AMBER}"' if i == 0 else ""
        chaps += (
            f'<div class="chap">'
            f'<div class="cnum" {cnum_color}>BET {i+1} &middot; {var_pct} of your risk</div>'
            f'<div class="cq">{name}</div>'
            + (f'<p class="ans">{desc}</p>' if desc else "")
            + "</div>"
        )

    # DATA-GAP note
    gap_note = ""
    if pc_gap:
        gap_note = (
            f'<div style="margin-top:8px;background:#f7fafb;border:1px solid {_LINE};'
            f"border-left:4px solid {_G1};border-radius:9px;padding:11px 13px;"
            f'font-size:12px;color:#33474c;line-height:1.55">'
            "<b>DATA-GAP:</b> not enough price history to name the underlying axes. "
            "Showing PCA variance shares only &#8212; the numbers are correct, "
            "the &#8220;what&#8221; behind each bet requires more data. "
            f"<span style=\"font-family:'IBM Plex Mono',monospace;font-size:9px;font-weight:600;"
            "background:#eef1f4;color:var(--risk-mut);padding:1px 6px;border-radius:5px;"
            'letter-spacing:.05em;margin-left:4px">DATA-GAP</span>'
            "</div>"
        )

    # Build the "how to raise" sector-gap action row using .act / .act .ic classes.
    # The first .act row is data-driven (sector_gaps); rows 2 and 3 are static guidance.
    if sector_gaps:
        levers_rows = (
            '<div class="act">'
            '<span class="ic">&#8593;</span>'
            f"<div><b>Add exposure on an axis you&#8217;re empty on.</b> "
            f"The book has zero weight in: "
            f'{", ".join(_html.escape(g) for g in sector_gaps)}. '
            "Adding any one loads a new principal portfolio &#8594; ENB rises. "
            f"<span style=\"font-family:'IBM Plex Mono',monospace;font-size:9px;font-weight:600;"
            "background:#eef1f4;color:var(--risk-mut);padding:1px 6px;border-radius:5px;"
            'letter-spacing:.05em">DESCRIPTIVE &middot; NOT A TRADE CALL</span>'
            "</div></div>"
        )
    else:
        levers_rows = (
            '<div class="act">'
            '<span class="ic">&#8593;</span>'
            "<div><b>Add exposure on an axis you&#8217;re empty on.</b> "
            "Diversify into an axis that moves differently from your current holdings &#8594; ENB rises. "
            "<span style=\"font-family:'IBM Plex Mono',monospace;font-size:9px;font-weight:600;"
            "background:#eef1f4;color:var(--risk-mut);padding:1px 6px;border-radius:5px;"
            'letter-spacing:.05em">DESCRIPTIVE &middot; NOT A TRADE CALL</span>'
            "</div></div>"
        )

    levers_html = (
        '<div class="levers" style="border-left-color:var(--risk-amber)">'
        '<div class="lvh">How to react &#8212; raise effective bets</div>'
        + levers_rows
        + '<div class="act">'
        '<span class="ic">&#10005;</span>'
        "<div><b>Don&#8217;t reshuffle within your largest bet.</b> "
        "Swapping one name for another on the same axis leaves ENB flat &#8212; it&#8217;s the same bet wearing a different ticker.</div>"
        "</div>"
        '<div class="act">'
        '<span class="ic">i</span>'
        "<div><b>This is descriptive, not advice.</b> "
        "It names the axes you lack; it does not tell you to enter any of them.</div>"
        "</div>"
        "</div>"
    )

    drill = (
        '<details class="teach" style="border-left-color:var(--risk-amber);margin-top:10px" open>'
        "<summary>"
        f'<span class="h">What are my ~{enb:.0f} bets, and how do I raise it?</span>'
        "<span>&#9660;</span>"
        "</summary>"
        '<div class="tbody">'
        f'<p class="ans" style="margin:6px 0 12px">'
        f"<b>&#8220;{enb:.1f} effective bets&#8221; means:</b> if you redrew your {total_h} "
        "holdings as a handful of <i>uncorrelated</i> wagers, you&#8217;d have about "
        f"{enb:.0f}. Names aren&#8217;t bets &#8212; <b>independent risks</b> are. "
        "Here&#8217;s what the bets actually are:</p>"
        + chaps
        + gap_note
        + levers_html
        + "</div></details>"
    )

    # Data-driven framing: the narrative must match the actual decomposition.
    # A book is "concentrated" only when one axis dominates the variance.
    concentrated = bool(pc_variance) and pc_variance[0] >= 0.40
    main_enb = (
        '<div class="risk-enb">'
        '<div class="risk-enbnum">'
        f'<div class="risk-big-n">{enb:.1f}</div>'
        f'<div class="risk-of">of {total_h} names</div>'
        '<div class="risk-lab">Effective bets</div>'
        "</div>"
        '<div class="risk-enbright">'
        f"<p>You hold {total_h} names, but the math says they behave like "
        f"<b>~{enb:.0f} independent bets</b>. The first principal portfolio "
        f"&#8212; essentially &#8220;{_bet_name(0)}&#8221; &#8212; "
        + (
            f"carries <b>{pc_variance[0]:.0%}</b> of your variance"
            f"{' &#8212; it dominates' if concentrated else ', the largest single share'}. "
            if pc_variance
            else "variance attribution is not yet available. "
        )
        + (
            "This is the rigorous version of the concentration flag: "
            "<b>one axis dominates</b> &#8212; you own &#8220;one thing, many ways.&#8221;</p>"
            if concentrated
            else "No single axis dominates &#8212; your risk is <b>genuinely spread</b> "
            "across many independent bets, not one. The concentration flag is about "
            "the systematic-share dial above, not this.</p>"
        )
        + pc_rows
        + "</div></div>"
    )

    return (
        f'<div class="ri-sec">How many real bets? {tooltip("Effective bets")}</div>'
        + main_enb
        + drill
    )
