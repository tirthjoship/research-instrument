"""Section 3 — how the week went. Descriptive only: factual moves, verdict flips,
adherence. No forecast surface."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import streamlit as st

from adapters.visualization.data_loader import load_adherence_log, load_brief_summary
from adapters.visualization.price_cache import fetch_week_changes
from application.holdings_reader import read_holdings


def _two_latest_snapshots(history_dir: str) -> list[dict[str, Any]]:
    files = sorted(Path(history_dir).glob("brief_*.json"))
    return [json.loads(f.read_text()) for f in files[-2:]]


def _verdict_flips(prev: dict[str, Any], cur: dict[str, Any]) -> list[str]:
    prev_v = {h["ticker"]: h["verdict"] for h in prev.get("holdings", [])}
    flips: list[str] = []
    for h in cur.get("holdings", []):
        was = prev_v.get(h["ticker"])
        if was and was != h["verdict"]:
            flips.append(f"{h['ticker']}: {was} → {h['verdict']}")
    return flips


def render(
    *,
    summary_path: str,
    holdings_path: str,
    adherence_log_path: str,
    history_dir: str,
) -> None:
    summary = load_brief_summary(summary_path)
    if summary is None:
        return
    st.subheader("How the week went")

    snaps = _two_latest_snapshots(history_dir)
    if len(snaps) < 2:
        st.caption("First week — nothing to compare yet.")
        return
    prev, cur = snaps[0], snaps[1]

    try:
        holdings = read_holdings(holdings_path)
    except (OSError, ValueError, KeyError):
        holdings = []
    tickers = tuple(h.ticker for h in holdings)
    changes = fetch_week_changes(tickers + ("SPY",)) if tickers else {}
    cols = st.columns(3)
    if changes and tickers:
        weights = {h.ticker: h.shares * h.cost_basis for h in holdings}
        total = sum(weights.values()) or 1.0
        book = sum(changes.get(t, 0.0) * w for t, w in weights.items()) / total
        spy = changes.get("SPY")
        with cols[0]:
            spy_txt = f" vs SPY {spy:+.1f}%" if spy is not None else ""
            st.metric("Book this week (cost-weighted)", f"{book:+.1f}%{spy_txt}")

    flips = _verdict_flips(prev, cur)
    with cols[1]:
        st.markdown(
            "**Verdict flips:** " + ("; ".join(flips) if flips else "none"),
        )

    adherence = load_adherence_log(adherence_log_path)
    with cols[2]:
        if adherence:
            last = adherence[-1]
            st.markdown(
                f"**Last adherence:** {last.get('ticker', '')} "
                f"{last.get('label', '')}"
            )
        else:
            st.markdown("**Last adherence:** no entries yet")
