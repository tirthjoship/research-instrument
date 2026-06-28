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
            "trailingPE": 52.0,
            "freeCashflow": 72e9,
            "marketCap": 4.2e12,
            "revenueGrowth": 0.69,
            "earningsGrowth": 0.82,
            "grossMargins": 0.75,
            "operatingMargins": 0.62,
            "profitMargins": 0.55,
            "returnOnEquity": 1.15,
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
            "priceToSalesTrailing12Months": 28.0,
            "enterpriseToEbitda": 45.0,
        },
        peer_percentiles={"P/E": 78.0},
        peer_data=[
            {"ticker": "AMD", "pe": 38.0, "revenue_growth": 0.30},
            {"ticker": "AVGO", "pe": 34.0, "revenue_growth": 0.20},
            {"ticker": "QCOM", "pe": 18.0, "revenue_growth": 0.10},
        ],
        analyst_panel=SimpleNamespace(
            count=42,
            mean_rating=1.6,
            target_mean=200.0,
            target_high=260.0,
            target_low=150.0,
            as_of="2026-06-27",
            data_gap=False,
        ),
        insider_transactions=[{"value": -48_000_000}],
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
            "followers": ["AMD"],
            "typical_lag_days": 3,
            "notes": "n",
            "_is_leader": True,
        },
        quarterly_financials=_qf6(),
        quarterly_cashflow=_qcf6(),
        quarterly_balance_sheet=None,
    )


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
    return pd.DataFrame(
        {
            c: {"Total Revenue": r, "Net Income": r * 0.55}
            for c, r in zip(_qcols(), revs)
        }
    )


def _qcf6():
    import pandas as pd

    fcfs = [46e9, 33e9, 28e9, 24e9, 20e9, 17e9]
    return pd.DataFrame({c: {"Free Cash Flow": f} for c, f in zip(_qcols(), fcfs)})


def render_doc(*, open_groups: bool = True) -> str:
    top = compose.build_top_html(nvda_result(), None, as_of="Jun 27 2026")
    if open_groups:  # headless Chrome won't expand <details>; force-open for panel QA
        top = top.replace("<details", "<details open")
    # Mimic Streamlit: block-container (1180px) wrapping the 800px sa-stage.
    return (
        "<!doctype html><html><head><meta charset=utf-8>"
        f"<style>{GLOBAL_CSS}</style>"
        "<style>body{margin:0;background:#F4F6F8}"
        ".block-container{max-width:1180px;margin:0 auto;padding:1rem 1.9rem 3rem}</style>"
        "</head><body><div class='block-container'>"
        f"{top}</div></body></html>"
    )


def main(widths: list[int]) -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    html_path = OUT / "tab.html"
    html_path.write_text(render_doc())
    for w in widths:
        png = OUT / f"tab_{w}.png"
        subprocess.run(
            [
                CHROME,
                "--headless=new",
                "--disable-gpu",
                "--hide-scrollbars",
                "--force-device-scale-factor=1",
                f"--screenshot={png}",
                f"--window-size={w},3000",
                f"file://{html_path}",
            ],
            check=False,
            capture_output=True,
        )
        print(f"  {w}px -> {png}")
    print(f"html: {html_path}")


if __name__ == "__main__":
    args = [int(a) for a in sys.argv[1:]] or [1280, 768, 414]
    main(args)
