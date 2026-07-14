"""Hero metric row for the portfolio tab."""

from __future__ import annotations

from adapters.visualization.components.tooltip import tooltip


def build_hero_html(
    *,
    book_value: float,
    cost: float,
    pnl: float,
    pnl_pct: float,
    spy_pct: float | None,
    needs_review: int,
    total_positions: int,
    top5: float,
) -> str:
    pnl_color = "var(--ri-green)" if pnl >= 0 else "var(--ri-crimson)"
    sign = "+" if pnl >= 0 else "-"
    abs_pnl = abs(pnl)
    badge = (
        f'<span style="font-size:.66rem;font-weight:700;padding:1px 6px;'
        f"border-radius:5px;background:#ECFDF5;color:var(--ri-green);"
        f'margin-left:4px;">vs SPY {"+" if spy_pct >= 0 else ""}{spy_pct:.1f}%</span>'
        if spy_pct is not None
        else ""
    )
    review_tip = tooltip("Needs review", "Needs review")
    conc_tip = tooltip("Concentration (top 5)", "Concentration")
    return (
        '<div class="ri-metric-row">'
        "<div>"
        '<div class="ri-metric-lab">Book value</div>'
        f'<div class="ri-metric-num">${book_value:,.0f}</div>'
        f'<div style="font-size:.72rem;color:var(--ri-muted);">cost ${cost:,.0f}</div>'
        "</div>"
        "<div>"
        '<div class="ri-metric-lab">Total P&amp;L</div>'
        f'<div class="ri-metric-num" style="color:{pnl_color};">{sign}${abs_pnl:,.0f}'
        f'<span style="font-size:.9rem;color:{pnl_color};margin-left:.4rem;">'
        f"({sign}{abs(pnl_pct):.1f}%)</span></div>"
        f'<div style="font-size:.72rem;">{badge}</div>'
        "</div>"
        "<div>"
        f'<div class="ri-metric-lab">{review_tip}</div>'
        f'<div class="ri-metric-num" style="color:#B45309;">{needs_review}</div>'
        f'<div style="font-size:.72rem;color:var(--ri-muted);">of {total_positions} positions</div>'
        "</div>"
        "<div>"
        f'<div class="ri-metric-lab">{conc_tip}</div>'
        f'<div class="ri-metric-num">{top5:.0f}%</div>'
        '<div style="font-size:.72rem;color:var(--ri-muted);">top 5 of book</div>'
        "</div>"
        "</div>"
    )
