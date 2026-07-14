#!/usr/bin/env python3
"""Render Buzz + Sentiment panels with live analysis data (preview HTML)."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from adapters.visualization.analysis.analyze import analyze_ticker  # noqa: E402
from adapters.visualization.components.styles import GLOBAL_CSS  # noqa: E402
from adapters.visualization.tabs.stock_analysis.buzz_view import (  # noqa: E402
    build_buzz_panel,
)
from adapters.visualization.tabs.stock_analysis.sentiment_view import (  # noqa: E402
    build_sentiment_panel,
)

_MOCKUP_CSS = """
body { margin: 0; padding: 24px; background: #f4f6f6; }
.wrap { max-width: 1180px; margin: 0 auto; }
.hdr { font-family: 'IBM Plex Sans', sans-serif; margin: 0 0 6px; font-size: 22px; }
.sub { color: #5c6b73; font-size: 13px; margin: 0 0 20px; }
.stack > .sa-panel { margin-bottom: 18px; }
.badge { display: inline-block; background: #e8f5e9; color: #1b5e20; font-size: 11px;
  padding: 4px 10px; border-radius: 999px; margin-bottom: 16px; }
"""


def main() -> None:
    ticker = (sys.argv[1] if len(sys.argv) > 1 else "NVDA").upper()
    out = (
        Path(sys.argv[2])
        if len(sys.argv) > 2
        else ROOT / "data" / "reports" / f"buzz-sentiment-{ticker.lower()}-preview.html"
    )
    out.parent.mkdir(parents=True, exist_ok=True)

    result = analyze_ticker(ticker)
    buzz = build_buzz_panel(result)
    sent = build_sentiment_panel(result)

    news = social = 0
    for sig in getattr(result, "buzz_signals", []) or []:
        src = str(getattr(sig, "source", "") or "").lower()
        cnt = int(getattr(sig, "mention_count", 0) or 0)
        if "reddit" in src:
            social += cnt
        else:
            news += cnt

    html = f"""<!DOCTYPE html>
<html lang="en"><head>
<meta charset="utf-8"/>
<meta name="viewport" content="width=device-width, initial-scale=1"/>
<title>Buzz + Sentiment — {ticker} (live)</title>
{GLOBAL_CSS}
<style>{_MOCKUP_CSS}</style>
</head><body>
<div class="wrap">
  <h1 class="hdr">Stock Analysis · {ticker} — Buzz &amp; Sentiment (live harvest)</h1>
  <p class="sub">Rendered from SQLite + yfinance at analysis time — not illustrative mock data.</p>
  <span class="badge">News/social mix in 30d window: {news}/{social}</span>
  <div class="stack">
    {buzz}
    {sent}
  </div>
</div>
</body></html>"""
    out.write_text(html, encoding="utf-8")
    print(out)


if __name__ == "__main__":
    main()
