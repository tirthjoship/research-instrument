"""Sector, who-owns, drift, teach sections."""

from __future__ import annotations

import html as _html
from typing import Any

from adapters.visualization.components.tooltip import tooltip
from domain.risk_rubric import classify_net_beta

from ._theme import *  # noqa: F403, F405
from .components import _flag_short


def _sector_section(macro: dict[str, Any]) -> str:
    """GICS sector weights + HHI + sector gaps tagged NOT A TRADE CALL."""
    sector_weights: dict[str, float] = macro.get("sector_weights") or {}
    sector_hhi = macro.get("sector_hhi")
    sector_gaps: list[str] = macro.get("sector_gaps") or []

    if not sector_weights:
        return (
            f'<div class="ri-sec">{tooltip("GICS sector", "Sector concentration")}</div>'
            f'<div class="barwrap" style="background:{_CARD};border:1px solid {_LINE};'
            f'border-radius:14px;padding:18px 20px">'
            f'<p style="font-size:12px;color:{_MUT}">DATA-GAP: sector weights not available &#8212; '
            "run weekly-brief to populate.</p>"
            "</div>"
        )

    max_w = max(sector_weights.values()) if sector_weights else 1.0
    rows = ""
    for sector, w in sorted(sector_weights.items(), key=lambda kv: kv[1], reverse=True):
        bar_pct = w / max_w * 100.0
        rows += (
            f'<div class="risk-wrow">'
            f'<span class="risk-wn">{_html.escape(sector)}</span>'
            f'<span class="risk-wt"><span class="risk-wf" style="width:{bar_pct:.0f}%"></span></span>'
            f'<span class="risk-wv">{w:.0%}</span>'
            "</div>"
        )

    hhi_note = ""
    if sector_hhi is not None:
        hhi_label = (
            "HIGH" if sector_hhi > 0.25 else "MODERATE" if sector_hhi > 0.15 else "LOW"
        )
        hhi_note = (
            f"<div style=\"font-family:'IBM Plex Mono',monospace;font-size:10.5px;"
            f"color:{_FAINT};margin-top:8px;border-top:1px dashed {_LINE};"
            'padding-top:9px;display:flex;align-items:center">'
            f'{tooltip("HHI", "Concentration (HHI)")}&nbsp;= {sector_hhi:.2f} &middot; {hhi_label}'
            "</div>" + _metric_evidence("sector_hhi")
        )

    gap_note = ""
    if sector_gaps:
        gaps_str = ", ".join(f"<b>0% {_html.escape(g)}</b>" for g in sector_gaps)
        gap_note = (
            f'<div style="margin-top:12px;background:#f7fafb;border:1px solid {_LINE};'
            f"border-left:4px solid {_G1};border-radius:10px;padding:11px 13px;"
            f'font-size:12px;color:#33474c;line-height:1.55">'
            "<b>Diversification gaps (descriptive):</b> the book holds "
            + gaps_str
            + ". Historically these sectors have moved less in step with a tech-and-growth bet "
            "than the sectors already held. "
            "<span style=\"font-family:'IBM Plex Mono',monospace;font-size:9px;font-weight:600;"
            "background:#eef1f4;color:var(--risk-mut);padding:1px 6px;border-radius:5px;"
            'letter-spacing:.05em;margin-left:4px">DESCRIPTIVE &middot; NOT A TRADE CALL</span>'
            '<br><span style="font-size:11px;color:var(--risk-mut)">'
            "This names where you have no exposure &#8212; it does not recommend entering any sector."
            "</span>"
            "</div>"
        )

    top3_pct = sum(sorted(sector_weights.values(), reverse=True)[:3])

    return (
        f'<div class="ri-sec">{tooltip("GICS sector", "Sector concentration")}</div>'
        f'<div class="barwrap" style="background:{_CARD};border:1px solid {_LINE};'
        'border-radius:14px;padding:18px 20px">'
        f'<p class="bcap2" style="font-size:12px;color:{_MUT};line-height:1.55;margin:0 0 12px">'
        f"Where the book clusters by industry (GICS). "
        f"<b>Top-3 sectors = {top3_pct:.0%}</b> of the book &#8212; the concentration flag "
        "isn&#8217;t just &#8220;the market,&#8221; it&#8217;s the sector tilt.</p>"
        + rows
        + hhi_note
        + gap_note
        + "</div>"
    )


def _who_owns(macro: dict[str, Any]) -> str:
    """Marginal risk contribution vs dollar weight — RISK &#8800; $ contrast."""
    risk_contribution: dict[str, float] = macro.get("risk_contribution") or {}
    holdings_meta: list[dict[str, Any]] = macro.get("holdings_meta") or []
    coverage_h = macro.get("coverage_holdings", "?")
    total_h = macro.get("total_holdings", "?")

    if not risk_contribution:
        return (
            f'<div class="ri-sec">Who owns the bet '
            f"<span style=\"font-family:'IBM Plex Mono',monospace;font-size:8px;font-weight:700;"
            f"letter-spacing:.08em;background:{_PETROL};color:#fff;"
            'padding:1px 6px;border-radius:6px;margin-left:8px;vertical-align:middle">RISK &#8800; $</span> '
            f'{tooltip("Risk contribution", "ⓘ")}'
            f"</div>"
            f'<div class="barwrap" style="background:{_CARD};border:1px solid {_LINE};'
            f'border-radius:14px;padding:18px 20px">'
            f'<p style="font-size:12px;color:{_MUT}">DATA-GAP: risk contribution not available &#8212; '
            "run weekly-brief to populate.</p>"
            "</div>"
        )

    # Build name→meta lookup
    meta_lookup: dict[str, dict[str, Any]] = {
        str(m.get("ticker", "")): m for m in holdings_meta
    }

    # Sort by risk contribution descending
    sorted_rc = sorted(risk_contribution.items(), key=lambda kv: kv[1], reverse=True)
    max_rc = sorted_rc[0][1] if sorted_rc else 1.0

    rows = ""
    for ticker, rc in sorted_rc[:5]:
        meta = meta_lookup.get(ticker, {})
        name = str(meta.get("name", ticker))
        bar_pct = rc / max_rc * 100.0

        rows += (
            f'<div class="risk-wrow">'
            f'<span class="risk-wn">{_html.escape(ticker)} '
            f"<span style=\"color:{_FAINT};font-family:'IBM Plex Sans',sans-serif;font-size:9.5px\">{_html.escape(name)}</span>"
            "</span>"
            f'<span class="risk-wt"><span class="risk-wf" style="width:{bar_pct:.0f}%"></span></span>'
            f'<span class="risk-wv">{rc:.0%}</span>'
            "</div>"
        )

    # Find a good contrast example for the caption
    caption_example = ""
    for ticker, rc in sorted_rc[:1]:
        meta = meta_lookup.get(ticker, {})
        weight = meta.get("weight")
        if weight is not None:
            caption_example = (
                f"{ticker} is <b>{rc:.0%} of risk on ~{float(weight):.0%} of dollars</b> "
                "(higher volatility), so it punches above its size. "
            )

    uncovered = (
        int(total_h) - int(coverage_h)
        if isinstance(total_h, int) and isinstance(coverage_h, int)
        else "?"
    )

    gap_note = (
        f"<div style=\"font-family:'IBM Plex Mono',monospace;font-size:10.5px;"
        f"color:{_FAINT};margin-top:8px;border-top:1px dashed {_LINE};"
        'padding-top:9px;display:flex;align-items:center">'
        f"TOP {min(5, len(sorted_rc))} = ~{sum(rc for _,rc in sorted_rc[:5]):.0%} OF SYSTEMATIC RISK "
        f"&middot; {uncovered} HOLDINGS UNCOVERED "
        f"<span style=\"font-family:'IBM Plex Mono',monospace;font-size:9px;font-weight:600;"
        "background:#eef1f4;color:var(--risk-mut);padding:1px 6px;border-radius:5px;"
        'letter-spacing:.05em;margin-left:8px">DATA-GAP</span>'
        "</div>"
    )

    return (
        f'<div class="ri-sec">Who owns the bet '
        f"<span style=\"font-family:'IBM Plex Mono',monospace;font-size:8px;font-weight:700;"
        f"letter-spacing:.08em;background:{_PETROL};color:#fff;"
        'padding:1px 6px;border-radius:6px;margin-left:8px;vertical-align:middle">RISK &#8800; $</span> '
        f'{tooltip("Risk contribution", "ⓘ")}'
        f"</div>"
        f'<div class="barwrap" style="background:{_CARD};border:1px solid {_LINE};'
        'border-radius:14px;padding:18px 20px">'
        f'<p class="bcap2" style="font-size:12px;color:{_MUT};line-height:1.55;margin:0 0 12px">'
        "Each holding's share of <b>portfolio risk</b> (variance), summing to 100% &#8212; "
        "<b>not dollar weight</b>. "
        + caption_example
        + "Trimming the biggest risk owners clears the flag fastest.</p>"
        + '<p style="font-size:10.5px;color:var(--risk-mut);margin:0 0 10px">'
        + "Right column = % of portfolio risk (Euler decomposition), not % of dollars"
        + "</p>"
        + rows
        + gap_note
        + "</div>"
    )


def _decision_levers(macro: dict[str, Any]) -> str:
    """Impact-ranked leverage on the concentration metrics — descriptive, not advice.

    Reuses the existing Euler risk-contribution decomposition (``risk_contribution``)
    and dollar weights (``holdings_meta``).  Ranks holdings by their share of
    portfolio risk (impact) and annotates risk-per-dollar leverage.  Frames each as
    *what moves the metric* (toward more spread / the 60% line), explicitly NOT a
    trade recommendation.  Returns ``""`` when the decomposition is unavailable.
    """
    risk_contribution: dict[str, float] = macro.get("risk_contribution") or {}
    if not risk_contribution:
        return ""

    holdings_meta: list[dict[str, Any]] = macro.get("holdings_meta") or []
    meta_lookup: dict[str, dict[str, Any]] = {
        str(m.get("ticker", "")): m for m in holdings_meta
    }
    sys_share = macro.get("systematic_share")

    sorted_rc = sorted(risk_contribution.items(), key=lambda kv: kv[1], reverse=True)

    # Gap framing: how far systematic share sits from the 60% line (directional only).
    gap_html = ""
    if sys_share is not None:
        share_pct = float(sys_share) * 100.0
        if share_pct >= 60.0:
            gap_html = (
                f'<p style="font-size:12px;color:#33474c;line-height:1.55;margin:0 0 12px">'
                f"Systematic share sits at <b>{share_pct:.0f}%</b> &#8212; "
                f"<b>{share_pct - 60.0:.0f} points</b> past the 60% line. "
                "The names below own the most of that risk, so reducing the heaviest "
                "is where any change has the <b>most leverage</b> on every concentration "
                "metric above &#8212; directionally toward more spread.</p>"
            )
        else:
            gap_html = (
                f'<p style="font-size:12px;color:#33474c;line-height:1.55;margin:0 0 12px">'
                f"Systematic share sits at <b>{share_pct:.0f}%</b> &#8212; "
                f"<b>{60.0 - share_pct:.0f} points</b> of headroom under the 60% line. "
                "The names below own the most of the book's risk, so they are where any "
                "change has the <b>most leverage</b> on the concentration metrics above.</p>"
            )

    rows = ""
    for rank, (ticker, rc) in enumerate(sorted_rc[:3], start=1):
        meta = meta_lookup.get(ticker, {})
        name = str(meta.get("name", ticker))
        weight = meta.get("weight")
        if weight is not None and float(weight) > 0.0:
            ratio = rc / float(weight)
            lev_txt = (
                f"owns <b>{rc:.0%} of portfolio risk</b> on "
                f"~{float(weight):.0%} of dollars "
                f"(&times;{ratio:.1f} risk-per-dollar)"
            )
        else:
            lev_txt = f"owns <b>{rc:.0%} of portfolio risk</b>"
        rows += (
            '<div class="act">'
            f'<span class="ic" style="background:{_PETROL};color:#fff;'
            "border-radius:6px;width:22px;height:22px;display:flex;align-items:center;"
            f'justify-content:center;font-weight:700">{rank}</span>'
            f"<div><b>{_html.escape(ticker)}</b> "
            f'<span style="color:{_FAINT};font-size:11px">{_html.escape(name)}</span> '
            f"&#8212; {lev_txt}. "
            + (
                "The single highest-leverage point on the concentration metrics."
                if rank == 1
                else "A secondary lever."
            )
            + "</div></div>"
        )

    return (
        '<div class="ri-sec" style="color:var(--risk-amber)">'
        "What moves the metric &middot; impact-ranked levers "
        f"{tooltip('Risk contribution', 'ⓘ')}</div>"
        '<div class="levers" style="border-left-color:var(--risk-amber)">'
        '<div class="lvh">Where a change has the most leverage</div>'
        + gap_html
        + rows
        + '<div class="act">'
        '<span class="ic">i</span>'
        "<div><b>This is descriptive leverage, not advice.</b> "
        "It ranks where the book's risk is concentrated &#8212; it does <b>not</b> tell "
        "you to trim any position or forecast what a change would return. "
        "<span style=\"font-family:'IBM Plex Mono',monospace;font-size:9px;font-weight:600;"
        "background:#eef1f4;color:var(--risk-mut);padding:1px 6px;border-radius:5px;"
        'letter-spacing:.05em">DESCRIPTIVE &middot; NOT A TRADE CALL</span></div></div>'
        "</div>"
    )


def _drift(macro: dict[str, Any]) -> str:
    """8-week sys_share history sparkline. Falls back to 'building history' if < 3 pts."""
    history: list[Any] = macro.get("sys_share_history") or []
    if len(history) < 3:
        return (
            '<div class="ri-sec"><span style="color:var(--risk-amber)">Flagged &middot;</span> '
            "Has it moved?</div>"
            f'<div class="risk-drift">'
            f'<div style="flex:1">'
            f'<div class="risk-dk">'
            f'{tooltip("Drift", "Systematic share &middot; drift")} &middot; last 8 weeks</div>'
            f'<div class="risk-dt" style="margin-top:6px">'
            "building history &#8212; fewer than 3 weeks of data available. "
            "Check back next week."
            "</div></div>"
            "</div>"
        )

    # Build a simple SVG sparkline
    values = [float(pt[1]) for pt in history[-8:]]
    dates = [str(pt[0]) for pt in history[-8:]]
    n = len(values)
    min_v = min(values)
    max_v = max(values)
    v_range = max_v - min_v if max_v > min_v else 0.01

    def _y(v: float) -> float:
        return 50.0 - (v - min_v) / v_range * 40.0  # 50 px height, 5px margin

    points = " ".join(f"{i*160/(n-1):.1f},{_y(v):.1f}" for i, v in enumerate(values))
    flag_y = _y(0.60)
    last_val = values[-1]
    first_val = values[0]
    trend_color = _AMBER if last_val > 0.60 else _G1

    spark_svg = (
        f'<svg class="spark" viewBox="0 0 160 56" preserveAspectRatio="none" '
        f'style="width:160px;height:56px;flex-shrink:0">'
        f'<line x1="0" y1="{flag_y:.1f}" x2="160" y2="{flag_y:.1f}" '
        f'stroke="{_AMBER}" stroke-dasharray="3 3" stroke-width="1" opacity=".55"/>'
        f'<polyline points="{points}" fill="none" stroke="{trend_color}" stroke-width="2.4"/>'
        f'<circle cx="160" cy="{_y(last_val):.1f}" r="3.6" fill="{trend_color}"/>'
        f'<text x="2" y="52" font-family="IBM Plex Mono" font-size="7" fill="{_FAINT}">'
        f"{_html.escape(dates[0])} {first_val:.0%}</text>"
        f'<text x="90" y="52" font-family="IBM Plex Mono" font-size="7" fill="{trend_color}">'
        f"now {last_val:.0%}</text>"
        "</svg>"
    )

    trend_dir = "climbing" if last_val > first_val else "falling"
    trend_text = (
        (
            f"The market bet is <b>{trend_dir}</b>: "
            f'<span class="risk-up">{first_val:.0%} &#8594; {last_val:.0%}</span> '
            f"over {n} weeks" + (", crossing the 60% line." if last_val > 0.60 else ".")
        )
        + " <b>Re-read the latest weekly brief</b> and confirm the tilt is intentional."
    )

    return (
        '<div class="ri-sec"><span style="color:var(--risk-amber)">Flagged &middot;</span> '
        "Has it moved?</div>"
        f'<div class="risk-drift">'
        '<div style="flex:1">'
        f'<div class="risk-dk">'
        f'Systematic share &middot; last 8 weeks {tooltip("Drift")}</div>'
        f'<div class="risk-dt" style="margin-top:6px">{trend_text}</div>'
        "</div>" + spark_svg + "</div>"
    )


def _teach(macro: dict[str, Any]) -> str:  # noqa: C901
    """Plain-English walkthrough card — data-driven from live macro."""
    # ── pull live values (degrade gracefully) ────────────────────────────────
    betas: dict[str, float] = macro.get("net_beta_by_factor") or {}
    spy_beta: float | None = betas.get("SPY")
    sys_share_raw = macro.get("systematic_share")
    idio_share_raw = macro.get("idiosyncratic_share")
    flags: list[str] = macro.get("flags") or []
    dominant_factor: str = macro.get("dominant_factor") or ""

    # ── Q1: net beta answer ───────────────────────────────────────────────────
    if spy_beta is None:
        q1_ans = '<p class="ans">DATA-GAP: net beta not available &#8212; run weekly-brief to populate.</p>'
    else:
        band = classify_net_beta(spy_beta)
        band_desc = band.value.lower()  # e.g. "market-like", "elevated"
        q1_ans = (
            f'<p class="ans"><b>{band_desc.capitalize()} market exposure '
            f"({spy_beta:+.2f}&times;)</b>. "
            "No defined line for size &#8212; so it&#8217;s grey.</p>"
        )

    # ── Q2: donut + verdict ───────────────────────────────────────────────────
    _SYS_THRESHOLD = 0.60
    if sys_share_raw is None or idio_share_raw is None:
        q2_body = (
            '<p class="csub">Systematic share: the fraction of variance from market-wide forces vs individual names.</p>'
            '<p class="ans">DATA-GAP: systematic / idiosyncratic shares not available.</p>'
        )
    else:
        sys_pct = int(round(float(sys_share_raw) * 100))
        idio_pct = int(round(float(idio_share_raw) * 100))
        flagged = float(sys_share_raw) >= _SYS_THRESHOLD
        sys_colour = _AMBER if flagged else _OK
        sys_label = "flagged bet" if flagged else "within line"
        idio_label = "within line" if flagged else "spread out"
        verdict_phrase = "One big bet" if flagged else "Spread out"
        if flagged:
            verdict_body = (
                f"<b>{verdict_phrase}</b> &#8212; the amber slice crossed the 60% line."
            )
        else:
            verdict_body = f"<b>{verdict_phrase}</b> &#8212; the stock-specific slice dominates (below the 60% line)."
        donut_html = (
            f'<div class="donut" style="background:conic-gradient({sys_colour} 0 {sys_pct}%,{_OK} {sys_pct}% 100%)">'
            f"<b>{sys_pct}%<span>SYSTEMATIC</span></b>"
            "</div>"
        )
        legend_html = (
            '<div class="dleg">'
            f'<span class="sw2" style="background:{sys_colour}"></span>'
            f"Systematic ({sys_label}) {sys_pct}%<br>"
            f'<span class="sw2" style="background:{_OK}"></span>'
            f"Stock-specific ({idio_label}) {idio_pct}%"
            "</div>"
        )
        q2_body = (
            '<p class="csub">Systematic share: the fraction of variance from market-wide forces vs individual names.</p>'
            f'<div class="split" style="margin-top:6px">'
            f"{donut_html}"
            f'<div style="flex:1">{legend_html}'
            f'<p class="ans" style="margin-top:8px">{verdict_body}</p>'
            "</div></div>"
        )

    # ── Q3: what's driving it ─────────────────────────────────────────────────
    # Build a concise factor summary using human-readable labels from _FACTOR_DISPLAY_NAMES
    long_labels: list[str] = []
    short_labels: list[str] = []
    for fname, fval in betas.items():
        if fname == "SPY":
            continue  # SPY is covered separately as "market"
        if abs(fval) >= 0.1:
            human = _FACTOR_DISPLAY_NAMES.get(fname, fname)
            if fval > 0:
                long_labels.append(human)
            else:
                short_labels.append(human)

    factor_parts: list[str] = []
    if long_labels:
        factor_parts.append("long " + " & ".join(long_labels))
    if short_labels:
        factor_parts.append("short " + " & ".join(short_labels))
    factor_str = ", ".join(factor_parts) if factor_parts else "factor exposures present"

    # Sector tilt note
    sector_weights: dict[str, float] = macro.get("sector_weights") or {}
    top_sector = (
        max(sector_weights, key=lambda k: sector_weights[k]) if sector_weights else None
    )
    sector_note = f"; {top_sector}-heavy" if top_sector else ""

    if dominant_factor:
        dom_human = _FACTOR_DISPLAY_NAMES.get(dominant_factor, dominant_factor)
        q3_ans = (
            f'<p class="ans"><b>Long market{", " + factor_str if factor_parts else ""}'
            f"{sector_note}.</b> "
            f"<b>{dom_human}</b> dwarfs everything.</p>"
        )
    else:
        q3_ans = (
            f'<p class="ans"><b>Long market{", " + factor_str if factor_parts else ""}'
            f"{sector_note}.</b> See the factor breakdowns above for the full picture.</p>"
        )

    # ── Q4: what to watch — dynamic from flags ────────────────────────────────
    n_flags = len(flags)
    if n_flags == 0:
        q4_sub = "Descriptive dials &#8212; no defined lines tripped this week."
        q4_body = (
            '<p class="ans">Nothing flagged &#8212; the dials are informational. '
            "Nothing here says to enter or exit positions.</p>"
        )
    else:
        shorts = [_flag_short(f) for f in flags]
        if n_flags == 1:
            tripped = f"one line tripped: <b>{shorts[0]}</b>"
        elif n_flags == 2:
            tripped = f"two lines tripped: <b>{shorts[0]}</b> and <b>{shorts[1]}</b>"
        else:
            joined = (
                ", ".join(f"<b>{s}</b>" for s in shorts[:-1])
                + f" and <b>{shorts[-1]}</b>"
            )
            tripped = f"{n_flags} lines tripped: {joined}"
        q4_sub = f"Descriptive dials &#8212; {tripped} this week."
        # Build bold-phrase list for Q4 confirmation line
        confirm_parts = [f"<b>{_flag_short(f)}</b>" for f in flags]
        confirm_str = " and ".join(confirm_parts)
        _verb = "is" if n_flags == 1 else "are"
        q4_body = (
            f'<p class="ans">Confirm the {confirm_str} '
            f"{_verb} intentional. Nothing here says to enter or exit positions.</p>"
        )

    return (
        '<div class="ri-sec" id="teach">'
        f'<span style="color:{_PETROL}">Teach me</span> &middot; The risk story</div>'
        '<details class="teach" open>'
        '<summary><span class="h">Plain-English walkthrough</span><span>&#8722;</span></summary>'
        '<div class="tbody">'
        # Q1
        '<div class="chap">'
        '<div class="cnum">QUESTION 1</div>'
        '<div class="cq">How much market am I holding?</div>'
        '<p class="csub">&#8220;Net beta&#8221; = how hard the book swings vs the market. 1.0 = step-for-step.</p>'
        f"{q1_ans}"
        "</div>"
        # Q2
        '<div class="chap">'
        '<div class="cnum">QUESTION 2</div>'
        '<div class="cq">Is it spread out, or one big bet?</div>'
        f"{q2_body}"
        "</div>"
        # Q3
        '<div class="chap">'
        '<div class="cnum">QUESTION 3</div>'
        '<div class="cq">What&#8217;s driving it?</div>'
        '<p class="csub">See the factor + sector breakdowns above.</p>'
        f"{q3_ans}"
        "</div>"
        # Q4
        '<div class="chap">'
        '<div class="cnum">QUESTION 4</div>'
        '<div class="cq">So what should I watch?</div>'
        f'<p class="csub">{q4_sub}</p>'
        f"{q4_body}"
        "</div>"
        "</div></details>"
    )
