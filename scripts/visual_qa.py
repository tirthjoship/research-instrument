#!/usr/bin/env python3
"""Deterministic visual-QA harness for the stock_analysis tab.

Renders ``build_top_html`` with a fixed NVDA fixture (same data as the mockup),
wraps it to mimic the Streamlit block-container, and screenshots it at several
viewport widths via headless Chrome. Use it to compare production against the
agreed mockup ground-truth and to check responsive reflow — no live dashboard,
no network, fully deterministic.

Usage:
    .venv/bin/python scripts/visual_qa.py            # widths 1280,768,414
    .venv/bin/python scripts/visual_qa.py 1280 600   # custom widths
    .venv/bin/python scripts/visual_qa.py tips       # force-show ⓘ tooltips
                                                     #   in the live Streamlit
                                                     #   nesting -> tip_check.png
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

from adapters.visualization.components.styles import GLOBAL_CSS
from adapters.visualization.tabs.stock_analysis import compose

CHROME = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
OUT = Path("/private/tmp/visual_qa")


def nvda_result() -> SimpleNamespace:
    """Fixed NVDA fixture mirroring the mockup data (kept in sync with test_sa_full_render)."""
    return SimpleNamespace(
        company_name="NVIDIA Corp",
        ticker="NVDA",
        sector="Semiconductors",
        current_price=172.0,
        change_pct=1.28,
        market_cap=4.2e12,
        info={
            "exchange": "NASDAQ",
            "fiftyTwoWeekLow": 86.6,
            "fiftyTwoWeekHigh": 189.5,
            "52WeekChange": 0.42,
            "SandP52WeekChange": 0.14,
            "beta": 1.7,
            "twoHundredDayAverage": 130.0,
            "fiftyDayAverage": 160.0,
            "heldPercentInstitutions": 0.66,
            "heldPercentInsiders": 0.04,
            # short primitives only (no shortPercentOfFloat/shortRatio) to exercise
            # the computed-fallback path -> ~1.1% short, ~1.0d to cover
            "sharesShort": 250e6,
            "floatShares": 23.5e9,
            "averageDailyVolume10Day": 250e6,
            "trailingPE": 52.0,
            "freeCashflow": 72e9,
            "marketCap": 4.2e12,
            "revenueGrowth": 0.69,
            "earningsGrowth": 0.82,
            "grossMargins": 0.75,
            "operatingMargins": 0.62,
            "profitMargins": 0.55,
            "returnOnEquity": 1.15,
            "returnOnAssets": 0.45,  # ROIC has no equity here -> tile shows ROA
            "totalRevenue": 130e9,
            "ebit": 80e9,
            "debtToEquity": 12.0,
            "totalCash": 43e9,
            "totalDebt": 9e9,
            "ebitda": 90e9,
            "interestExpense": 1e9,
            "currentRatio": 4.1,
            "quickRatio": 3.5,
            "pegRatio": 0.75,
            "forwardPE": 34.0,
            "forwardEps": 4.5,  # consensus forward EPS -> Analyst "Fwd EPS" tile
            "priceToSalesTrailing12Months": 28.0,
            "enterpriseToEbitda": 45.0,
        },
        peer_percentiles={"P/E": 78.0},
        peer_data=[
            {
                "ticker": "AMD",
                "pe": 38.0,
                "revenue_growth": 0.30,
                "gross_margins": 0.50,
            },
            {
                "ticker": "AVGO",
                "pe": 34.0,
                "revenue_growth": 0.20,
                "gross_margins": 0.62,
            },
            {
                "ticker": "QCOM",
                "pe": 18.0,
                "revenue_growth": 0.10,
                "gross_margins": 0.56,
            },
        ],
        rating_distribution={"r1": 30, "r2": 18, "r3": 8, "r4": 2, "r5": 0},
        annual_revenue=[27e9, 60e9, 130e9, 200e9],  # ~3y -> strong CAGR
        forward_revenue_growth=0.48,
        analyst_panel=SimpleNamespace(
            count=42,
            mean_rating=1.6,
            target_mean=200.0,
            target_high=260.0,
            target_low=150.0,
            as_of="2026-06-27",
            data_gap=False,
        ),
        insider_transactions=[
            {"value": -186_000_000, "Start Date": "2026-06-18"},
            {"value": -120_000_000, "Start Date": "2026-03-15"},
            {"value": -90_000_000, "Start Date": "2025-12-10"},
        ],
        buzz_signals=[
            SimpleNamespace(
                source="reddit",
                mention_count=30,
                sentiment_raw=0.3,
                fetched_at="2026-06-27",
            ),
        ],
        supply_chain_group={
            "group": "AI semis",
            "leaders": ["NVDA"],
            "followers": ["AMD", "AVGO", "TSM"],
            "typical_lag_days": 3,
            "notes": "n",
            "_is_leader": True,
            "member_moves": {"NVDA": 2.4, "AMD": -1.1, "AVGO": 0.8, "TSM": 1.5},
        },
        quarterly_financials=_qf6(),
        quarterly_cashflow=_qcf6(),
        quarterly_balance_sheet=_qbs6(),
        price_history=_price_history(),
    )


def _qbs6():
    import pandas as pd

    cash = [53e9, 48e9, 43e9, 38e9, 34e9, 30e9]  # newest-first
    debt = [12e9, 12.5e9, 13e9, 9e9, 9.5e9, 10e9]
    return pd.DataFrame(
        {
            c: {"Cash And Cash Equivalents": ca, "Total Debt": d}
            for c, ca, d in zip(_qcols(), cash, debt)
        }
    )


def _price_history() -> dict[str, object]:
    closes = [100 * (1.0009**i) for i in range(800)]
    closes[600:640] = [c * 0.72 for c in closes[600:640]]  # a visible drawdown
    spy = [400 * (1.0004**i) for i in range(800)]
    return {"closes": closes, "spy_closes": spy, "ma200": closes[-1], "atr": 5.0}


def _qcols() -> list[str]:
    return [
        "2026-03-31",
        "2025-12-31",
        "2025-09-30",
        "2025-06-30",
        "2025-03-31",
        "2024-12-31",
    ]


def _qf6():
    import pandas as pd

    revs = [57e9, 44e9, 35e9, 30e9, 26e9, 22e9]  # newest-first
    # gross/op margins drift up over time (newest-first highest) -> widening trend
    gm = [0.76, 0.75, 0.74, 0.73, 0.72, 0.70]
    om = [0.64, 0.63, 0.62, 0.60, 0.58, 0.56]
    return pd.DataFrame(
        {
            c: {
                "Total Revenue": r,
                "Net Income": r * 0.55,
                "Gross Profit": r * g,
                "Operating Income": r * o,
            }
            for c, r, g, o in zip(_qcols(), revs, gm, om)
        }
    )


def _qcf6():
    import pandas as pd

    fcfs = [46e9, 33e9, 28e9, 24e9, 20e9, 17e9]
    return pd.DataFrame({c: {"Free Cash Flow": f} for c, f in zip(_qcols(), fcfs)})


def _fit_fixture() -> object:
    """A FitVerdict mirroring the mockup so the snowflake/fit section renders.

    Without a fit object build_top_html degrades to the fit-card-only fallback
    (no radar). Pair this with _install_screen_stub so _snowflake_axes also
    finds the Value/Quality/Momentum/Revision/Trend factor scores.
    """
    from domain.fit import FitFlag, FitVerdict

    return FitVerdict(
        ticker="NVDA",
        evidence_grade="B",
        fit_flags=(
            FitFlag(
                "concentration", "Position would exceed your sector cap.", "WARNING"
            ),
            FitFlag("beta", "Beta 1.7 is above your portfolio target.", "CAUTION"),
            FitFlag("liquidity", "Liquidity is ample for entry.", "INFO"),
        ),
        summary="Strong evidence shape; two fit cautions for your book.",
    )


def _install_screen_stub() -> None:
    """Point load_latest_screen at an in-memory NVDA screen row so the radar's
    factor axes (Value/Quality/Momentum/Revision/Trend) populate — matches the
    mockup percentiles. Patches the data_loader symbol _snowflake_axes imports."""
    from adapters.visualization import data_loader

    screen = {
        "candidates": [
            {
                "ticker": "NVDA",
                "factor_scores": [
                    {"name": "value", "percentile": 0.22},
                    {"name": "quality", "percentile": 0.88},
                    {"name": "momentum", "percentile": 0.95},
                    {"name": "revision", "percentile": 0.80},
                ],
                "trend_health": 0.8,  # -> Trend filter 90
            }
        ]
    }
    data_loader.load_latest_screen = lambda *_a, **_k: screen  # type: ignore[assignment]


def render_doc(*, open_groups: bool = True, tips: bool = False) -> str:
    _install_screen_stub()
    top = compose.build_top_html(nvda_result(), _fit_fixture(), as_of="Jun 27 2026")
    if open_groups:  # headless Chrome won't expand <details>; force-open for panel QA
        top = top.replace("<details", "<details open")
    # `tips` mode reproduces the live Streamlit nesting (stVerticalBlock >
    # stMarkdown > stMarkdownContainer) and force-shows every .sa-tip, so the
    # ⓘ tooltips can be checked for container clipping deterministically — the
    # one thing a plain :hover-less screenshot can't otherwise confirm.
    force = (
        "<style>.sa-tip{opacity:1!important;visibility:visible!important;"
        "transform:translateX(-50%) translateY(0)!important}</style>"
        if tips
        else ""
    )
    body_open, body_close = "", ""
    if tips:
        body_open = (
            "<div data-testid='stVerticalBlock'>"
            "<div data-testid='stMarkdown'><div data-testid='stMarkdownContainer'>"
        )
        body_close = "</div></div></div>"
    # Mimic Streamlit: block-container (1180px) wrapping the 800px sa-stage.
    return (
        "<!doctype html><html><head><meta charset=utf-8>"
        f"<style>{GLOBAL_CSS}</style>{force}"
        "<style>body{margin:0;background:#F4F6F8}"
        ".block-container{max-width:1180px;margin:0 auto;padding:1rem 1.9rem 3rem}</style>"
        "</head><body><div class='block-container'>"
        f"{body_open}{top}{body_close}</div></body></html>"
    )


def main(widths: list[int], *, tips: bool = False) -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    stem = "tip_check" if tips else "tab"
    html_path = OUT / f"{stem}.html"
    html_path.write_text(render_doc(tips=tips))
    for w in widths:
        png = OUT / (f"{stem}.png" if tips else f"tab_{w}.png")
        subprocess.run(
            [
                CHROME,
                "--headless=new",
                "--disable-gpu",
                "--hide-scrollbars",
                "--force-device-scale-factor=1",
                f"--screenshot={png}",
                f"--window-size={w},6000",
                f"file://{html_path}",
            ],
            check=False,
            capture_output=True,
        )
        print(f"  {w}px -> {png}")
    print(f"html: {html_path}")


if __name__ == "__main__":
    raw = sys.argv[1:]
    tips = "tips" in raw
    args = [int(a) for a in raw if a.isdigit()] or (
        [1280] if tips else [1280, 768, 414]
    )
    main(args, tips=tips)
