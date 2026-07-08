#!/usr/bin/env python3
"""Render the Corroboration section with live analysis data (preview HTML).

Usage: render_corroboration_preview.py [TICKER] [OUT_PATH]

Always renders the live path (real store claims + a real OurReadout bridged
from analyze_ticker's AnalysisResult — no invented data). When the ticker has
zero harvested claims (harvest is search-driven, capped at 25 tickers — see
STATUS.md — so most tickers won't have claims on any given day), a SECOND
file is also written using 6 claims shaped like the design mockup (4 bullish,
1 neutral, 1 bearish dissent), clearly labelled ILLUSTRATIVE so it can never
be mistaken for live data.
"""

from __future__ import annotations

import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from adapters.visualization.analysis.analyze import analyze_ticker  # noqa: E402
from adapters.visualization.analysis.corroboration_bridge import (  # noqa: E402
    build_readout_from_analysis,
)
from adapters.visualization.components.styles import GLOBAL_CSS  # noqa: E402
from adapters.visualization.data_loader import (  # noqa: E402
    CorroborationTabView,
    load_corroboration_snapshot,
)
from adapters.visualization.tabs.stock_analysis.corroboration_section import (  # noqa: E402
    build_corroboration_html,
)
from adapters.visualization.tabs.stock_analysis.corroboration_view import (  # noqa: E402
    build_corroboration_view,
)
from domain.corroboration_models import (  # noqa: E402
    CandidateSnapshot,
    ConvergenceTier,
    DirectionalView,
    HarvestedClaim,
    Stance,
)

_MOCKUP_CSS = """
body { margin: 0; padding: 24px; background: #f4f6f6; }
.wrap { max-width: 820px; margin: 0 auto; }
.hdr { font-family: 'IBM Plex Sans', sans-serif; margin: 0 0 6px; font-size: 22px; }
.sub { color: #5c6b73; font-size: 13px; margin: 0 0 20px; }
.badge { display: inline-block; background: #e8f5e9; color: #1b5e20; font-size: 11px;
  padding: 4px 10px; border-radius: 999px; margin-bottom: 16px; }
.badge.illustrative { background: #fef3c7; color: #92400e; }
"""


def _page(title: str, badge: str, badge_class: str, body: str) -> str:
    return f"""<!DOCTYPE html>
<html lang="en"><head>
<meta charset="utf-8"/>
<meta name="viewport" content="width=device-width, initial-scale=1"/>
<title>{title}</title>
{GLOBAL_CSS}
<style>{_MOCKUP_CSS}</style>
</head><body>
<div class="wrap">
  <h1 class="hdr">{title}</h1>
  <span class="badge {badge_class}">{badge}</span>
  <div class="sa-panel">{body}</div>
</div>
</body></html>"""


def _illustrative_claims(ticker: str) -> tuple[HarvestedClaim, ...]:
    """6 claims shaped like the mockup: 4 bullish, 1 neutral, 1 bearish dissent."""
    return (
        HarvestedClaim(
            source_name="Reuters",
            ticker=ticker,
            stance=Stance.BULLISH,
            thesis_summary="Data-center order backlog extends well into next year.",
            url="https://example.com/illustrative-reuters",
            published_at=date(2026, 7, 6),
            verified=True,
            reliability_weight=0.85,
        ),
        HarvestedClaim(
            source_name="Company 10-K",
            ticker=ticker,
            stance=Stance.NEUTRAL,
            thesis_summary="Customer concentration risk explicitly disclosed.",
            url="https://example.com/illustrative-10k",
            published_at=date(2026, 7, 1),
            verified=True,
            reliability_weight=0.90,
        ),
        HarvestedClaim(
            source_name="Analyst note",
            ticker=ticker,
            stance=Stance.BULLISH,
            thesis_summary="Margin expansion likely to continue near-term.",
            url="https://example.com/illustrative-analyst",
            published_at=date(2026, 7, 5),
            verified=True,
            reliability_weight=0.65,
        ),
        HarvestedClaim(
            source_name="Trade press",
            ticker=ticker,
            stance=Stance.BULLISH,
            thesis_summary="Key supplier ramping capacity to meet demand.",
            url="https://example.com/illustrative-trade",
            published_at=date(2026, 7, 4),
            verified=False,
            reliability_weight=0.55,
        ),
        HarvestedClaim(
            source_name="Forum post",
            ticker=ticker,
            stance=Stance.BULLISH,
            thesis_summary="Retail chatter is bullish ahead of earnings.",
            url="https://example.com/illustrative-forum",
            published_at=date(2026, 7, 7),
            verified=False,
            reliability_weight=0.20,
        ),
        HarvestedClaim(
            source_name="Analyst B",
            ticker=ticker,
            stance=Stance.BEARISH,
            thesis_summary="Valuation is stretched relative to growth.",
            url="https://example.com/illustrative-bearish",
            published_at=date(2026, 7, 3),
            verified=True,
            reliability_weight=0.60,
        ),
    )


def _illustrative_view(ticker: str) -> CorroborationTabView:
    claims = _illustrative_claims(ticker)
    return CorroborationTabView(
        ticker=ticker,
        as_of=date.today(),
        claims=claims,
        snapshot=CandidateSnapshot(
            ticker=ticker,
            convergence=ConvergenceTier.MODERATE,
            verification="PARTIAL",
            mean_convergence=0.6,
        ),
        our_readout=None,
        directional_views=(
            DirectionalView(
                group_kind="sector",
                group_name="Evidence consensus",
                net_stance=Stance.BULLISH,
                mean_convergence=0.65,
                your_exposure_pct=0.0,
                evidence_weight_pct=0.65,
                tilt="HOLD",
            ),
        ),
    )


def main() -> None:
    ticker = (sys.argv[1] if len(sys.argv) > 1 else "NVDA").upper()
    out = (
        Path(sys.argv[2])
        if len(sys.argv) > 2
        else ROOT / "data" / "reports" / f"corroboration-{ticker.lower()}-preview.html"
    )
    out.parent.mkdir(parents=True, exist_ok=True)

    result = analyze_ticker(ticker)
    readout = build_readout_from_analysis(result)
    corr_view = load_corroboration_snapshot(ticker)
    view = build_corroboration_view(corr_view, our_readout=readout)
    live_html = build_corroboration_html(view)

    n_claims = len(corr_view.claims) if corr_view is not None else 0
    live_page = _page(
        f"Corroboration — {ticker} (live)",
        f"{n_claims} claim{'s' if n_claims != 1 else ''} from data/recommendations.db",
        "",
        live_html,
    )
    out.write_text(live_page, encoding="utf-8")
    print(out)

    if n_claims == 0:
        mock_view = build_corroboration_view(
            _illustrative_view(ticker), our_readout=readout
        )
        mock_html = build_corroboration_html(mock_view)
        mock_page = _page(
            f"Corroboration — {ticker} (ILLUSTRATIVE)",
            "ILLUSTRATIVE — 6 mockup-shaped claims, not from the live store",
            "illustrative",
            mock_html,
        )
        mock_out = ROOT / "data" / "reports" / "corroboration-mock-preview.html"
        mock_out.write_text(mock_page, encoding="utf-8")
        print(mock_out)


if __name__ == "__main__":
    main()
