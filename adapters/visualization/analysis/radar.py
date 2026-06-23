"""Signal radar and insider aggregation helpers."""

from __future__ import annotations

from collections import defaultdict
from typing import Any


def compute_signal_radar(
    info: dict[str, Any],
    buzz: list[Any],
    rec: Any,
    sc_group: dict[str, Any] | None,
    insider_txns: list[dict[str, Any]],
) -> dict[str, float]:
    """Compute 0-10 scores for the 6 signal radar dimensions."""
    scores: dict[str, float] = {}

    # Technical (0-10): based on RSI/momentum proxies from info
    tech_score = 5.0
    pe = info.get("trailingPE")
    roe = info.get("returnOnEquity")
    rev_growth = info.get("revenueGrowth")
    beta = info.get("beta", 1.0) or 1.0
    if pe and pe < 25:
        tech_score += 1
    if roe and roe > 0.15:
        tech_score += 1
    if rev_growth and rev_growth > 0:
        tech_score += 1
    if beta < 1.5:
        tech_score += 0.5
    if pe and pe > 40:
        tech_score -= 1
    scores["Technical"] = min(10.0, max(0.0, tech_score))

    # Sentiment (0-10)
    if buzz:
        sentiments = [float(getattr(b, "sentiment_raw", 0)) for b in buzz]
        avg_sent = sum(sentiments) / len(sentiments) if sentiments else 0
        # Map [-1, 1] → [0, 10]
        sent_score = (avg_sent + 1) / 2 * 10
        sent_score = min(10.0, max(0.0, sent_score))
    else:
        sent_score = 5.0
    scores["Sentiment"] = sent_score

    # Fundamental (0-10): from scoring function
    fundamental_score = 5.0
    if info.get("freeCashflow") and (info.get("freeCashflow") or 0) > 0:
        fundamental_score += 1
    if info.get("profitMargins") and (info.get("profitMargins") or 0) > 0.10:
        fundamental_score += 1
    if info.get("returnOnEquity") and (info.get("returnOnEquity") or 0) > 0.15:
        fundamental_score += 1
    if info.get("debtToEquity") and (info.get("debtToEquity") or 999) < 100:
        fundamental_score += 1
    if info.get("pegRatio") and (info.get("pegRatio") or 99) < 2:
        fundamental_score += 1
    scores["Fundamental"] = min(10.0, max(0.0, fundamental_score))

    # Cross-Asset (0-10): from supply chain group membership
    if sc_group:
        total = len(sc_group.get("leaders", [])) + len(sc_group.get("followers", []))
        cross_score = min(10.0, 5.0 + total * 0.3)
    else:
        cross_score = 3.0
    scores["Cross-Asset"] = cross_score

    # Event-Causal (0-10): from recommendation data
    if rec and hasattr(rec, "composite_score"):
        event_score = float(getattr(rec, "composite_score", 0.5)) * 10
    else:
        event_score = 5.0
    scores["Event-Causal"] = min(10.0, max(0.0, event_score))

    # Smart Money (0-10): from insider transactions
    if insider_txns:
        buys = sum(
            1
            for t in insider_txns
            if str(t.get("transactionType", t.get("Transaction", ""))).lower()
            in ("buy", "purchase")
        )
        total = len(insider_txns)
        buy_ratio = buys / total if total > 0 else 0.5
        smart_score = buy_ratio * 10
    else:
        smart_score = 5.0
    inst_pct = info.get("heldPercentInstitutions", 0.5) or 0.5
    smart_score = (smart_score + inst_pct * 10) / 2
    scores["Smart Money"] = min(10.0, max(0.0, smart_score))

    return scores


def aggregate_insider_by_quarter(
    insider_txns: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    """Aggregate insider transactions by quarter for insider_bars chart.

    Returns list of {quarter, buys, sells, buy_value, sell_value}.
    """
    quarters: dict[str, dict[str, Any]] = defaultdict(
        lambda: {"buys": 0, "sells": 0, "buy_value": 0.0, "sell_value": 0.0}
    )
    for txn in insider_txns:
        try:
            date_val = (
                txn.get("Date") or txn.get("startDate") or txn.get("dateReported")
            )
            if date_val is None:
                continue
            if hasattr(date_val, "year"):
                year = date_val.year
                month = date_val.month
            else:
                from datetime import datetime

                dt = datetime.fromisoformat(str(date_val)[:10])
                year = dt.year
                month = dt.month
            quarter = f"Q{(month - 1) // 3 + 1} {year}"

            txn_type = str(
                txn.get("transactionType", txn.get("Transaction", ""))
            ).lower()
            value = abs(float(txn.get("Value", txn.get("value", 0)) or 0))
            if "buy" in txn_type or "purchase" in txn_type:
                quarters[quarter]["buys"] += 1
                quarters[quarter]["buy_value"] += value
            else:
                quarters[quarter]["sells"] += 1
                quarters[quarter]["sell_value"] += value
        except Exception:
            continue

    result = [{"quarter": k, **v} for k, v in sorted(quarters.items())]
    return result[-8:]  # Last 8 quarters
