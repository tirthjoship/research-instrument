#!/usr/bin/env python3
"""Render the Supply Chain panel with live analysis data (preview HTML)."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from adapters.visualization.analysis.analyze import analyze_ticker  # noqa: E402
from adapters.visualization.components.styles import GLOBAL_CSS  # noqa: E402
from adapters.visualization.tabs.stock_analysis.supply_chain_view import (  # noqa: E402
    build_supply_chain_panel,
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
        else ROOT / "data" / "reports" / f"supply-chain-{ticker.lower()}-preview.html"
    )
    out.parent.mkdir(parents=True, exist_ok=True)

    result = analyze_ticker(ticker)
    panel = build_supply_chain_panel(result)

    grp = result.supply_chain_group or {}
    group_display = grp.get("group_display", "—")
    provenance = grp.get("provenance", "—")
    role = "Leader" if grp.get("_is_leader") else "Follower"

    html = f"""<!DOCTYPE html>
<html lang="en"><head>
<meta charset="utf-8"/>
<meta name="viewport" content="width=device-width, initial-scale=1"/>
<title>Supply Chain — {ticker} (live)</title>
{GLOBAL_CSS}
<style>{_MOCKUP_CSS}</style>
</head><body>
<div class="wrap">
  <h1 class="hdr">Stock Analysis · {ticker} — Supply Chain (dynamic resolution)</h1>
  <p class="sub">Rendered from resolve_supply_chain_group() + yfinance at analysis time — not illustrative mock data.</p>
  <span class="badge">Group: {group_display} · Role: {role} · Provenance: {provenance}</span>
  <div class="stack">
    {panel}
  </div>
</div>
</body></html>"""
    out.write_text(html, encoding="utf-8")
    print(out)


if __name__ == "__main__":
    main()
