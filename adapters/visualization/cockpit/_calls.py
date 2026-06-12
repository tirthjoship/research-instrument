"""Section 2 — this week's per-holding calls + the cockpit's single write action.

Replaces the old My Portfolio forms: one confirm step logs the week's verdicts
to the ADR-048 discipline forward gate (idempotent per as_of) and snapshots the
brief for next week's retro strip.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import streamlit as st

from adapters.visualization.data_loader import load_brief_summary
from adapters.visualization.price_cache import fetch_prices
from application.discipline_log import append_assessments, read_assessments
from application.holdings_reader import read_holdings

_VERDICT_CLASS = {
    "REDUCE": "verdict-negative",
    "TRIM": "verdict-caution",
    "REVIEW": "verdict-neutral",
    "HOLD": "verdict-neutral",
    "ADD_OK": "verdict-positive",
}


def already_logged(summary: dict[str, Any], discipline_log_path: str) -> bool:
    as_of = summary.get("as_of", "")
    return any(r.get("as_of") == as_of for r in read_assessments(discipline_log_path))


def confirm_and_log(
    *,
    summary: dict[str, Any],
    holdings_path: str,
    discipline_log_path: str,
    history_dir: str,
) -> None:
    if not summary.get("as_of"):
        # No as_of -> idempotency key is empty; every confirm would collide and
        # the snapshot filename would degrade to "brief_.json". Refuse the write.
        return
    if already_logged(summary, discipline_log_path):
        return
    qty = {h.ticker: h.shares for h in _safe_holdings(holdings_path)}
    tickers = tuple(h["ticker"] for h in summary.get("holdings", []))
    prices = fetch_prices(tickers) if tickers else {}
    rows: list[dict[str, Any]] = []
    for h in summary.get("holdings", []):
        t = h["ticker"]
        price = float(prices.get(t, {}).get("price") or 0.0)
        q = float(qty.get(t, 0.0))
        rows.append(
            {
                "ticker": t,
                "verdict": h["verdict"],
                "price": price,
                "trend_health": None,
                "as_of": summary.get("as_of", ""),
                "quantity": q,
                "market_value_cad": price * q if price and q else None,
            }
        )
    append_assessments(discipline_log_path, rows)
    hist = Path(history_dir)
    hist.mkdir(parents=True, exist_ok=True)
    stamp = str(summary.get("as_of", ""))[:10]
    (hist / f"brief_{stamp}.json").write_text(json.dumps(summary))


def _safe_holdings(path: str) -> list[Any]:
    try:
        return read_holdings(path)
    except (OSError, ValueError, KeyError):
        return []


def render(
    *,
    summary_path: str,
    holdings_path: str,
    discipline_log_path: str,
    history_dir: str,
) -> None:
    summary = load_brief_summary(summary_path)
    if summary is None or not summary.get("holdings"):
        st.info("No calls this week — the weekly brief has no holdings verdicts.")
        return

    st.subheader("Your calls this week")
    for h in summary["holdings"]:
        cls = _VERDICT_CLASS.get(h["verdict"], "verdict-neutral")
        st.markdown(
            f'<div class="verdict-card {cls}">'
            f'<strong>{h["ticker"]}</strong> — {h["verdict"]} · '
            f'{h.get("unrealized_pct", 0.0):+.1f}% · {h.get("trend_state", "")}'
            f'<br><span style="color:var(--text-secondary);">{h.get("why", "")}</span>'
            "</div>",
            unsafe_allow_html=True,
        )

    if not summary.get("as_of"):
        st.caption("This brief has no as-of date — logging is disabled until it does.")
    elif already_logged(summary, discipline_log_path):
        st.success("This week's calls are logged to the discipline gate.")
    elif st.button("Confirm all — log this week's calls", key="cp_confirm_all"):
        confirm_and_log(
            summary=summary,
            holdings_path=holdings_path,
            discipline_log_path=discipline_log_path,
            history_dir=history_dir,
        )
        st.rerun()
