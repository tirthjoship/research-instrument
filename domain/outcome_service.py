"""Outcome tracking service — pure domain logic.

Computes trade outcomes, signal performance aggregations, and plain-text
report cards.  Only stdlib imports allowed in domain/.
"""

from __future__ import annotations

from collections import defaultdict
from datetime import date
from typing import DefaultDict

from domain.outcome import SignalPerformance, TrackedTrade, TradeOutcome


def compute_outcome(buy: TrackedTrade, sell: TrackedTrade) -> TradeOutcome:
    """Compute a completed round-trip trade outcome.

    Args:
        buy: The opening (BUY) TrackedTrade.
        sell: The closing (SELL) TrackedTrade.

    Returns:
        A TradeOutcome with return metrics and holding period.

    Raises:
        ValueError: If buy and sell tickers do not match.
    """
    if buy.ticker != sell.ticker:
        raise ValueError(f"ticker mismatch: buy={buy.ticker!r} vs sell={sell.ticker!r}")

    buy_date = date.fromisoformat(buy.trade_date)
    sell_date = date.fromisoformat(sell.trade_date)
    holding_days = (sell_date - buy_date).days

    return_pct = ((sell.price - buy.price) / buy.price) * 100.0
    return_dollar = (sell.price - buy.price) * buy.quantity

    return TradeOutcome(
        ticker=buy.ticker,
        buy_trade_id=buy.trade_id,
        sell_trade_id=sell.trade_id,
        buy_price=buy.price,
        sell_price=sell.price,
        quantity=buy.quantity,
        buy_date=buy.trade_date,
        sell_date=sell.trade_date,
        holding_days=holding_days,
        return_pct=return_pct,
        return_dollar=return_dollar,
        signals_at_entry=list(buy.signals_at_trade),
        conviction_at_entry=buy.conviction_at_trade,
    )


def compute_signal_performance(
    outcomes: list[TradeOutcome],
) -> list[SignalPerformance]:
    """Aggregate performance statistics grouped by signal name.

    Each outcome may carry multiple signals; each signal accumulates stats
    independently.

    Args:
        outcomes: List of completed TradeOutcome records.

    Returns:
        One SignalPerformance per unique signal name, or an empty list if
        outcomes is empty.
    """
    if not outcomes:
        return []

    # Accumulator buckets keyed by signal name
    returns: DefaultDict[str, list[float]] = defaultdict(list)

    for outcome in outcomes:
        for signal in outcome.signals_at_entry:
            returns[signal].append(outcome.return_pct)

    performances: list[SignalPerformance] = []
    for signal_name, rets in returns.items():
        winning = [r for r in rets if r > 0]
        losing = [r for r in rets if r <= 0]
        total = len(rets)
        hit_rate = (len(winning) / total) * 100.0 if total else 0.0
        avg_return = sum(rets) / total if total else 0.0
        avg_winning = sum(winning) / len(winning) if winning else 0.0
        avg_losing = sum(losing) / len(losing) if losing else 0.0

        performances.append(
            SignalPerformance(
                signal_name=signal_name,
                total_trades=total,
                winning_trades=len(winning),
                losing_trades=len(losing),
                hit_rate=hit_rate,
                avg_return_pct=avg_return,
                avg_winning_return=avg_winning,
                avg_losing_return=avg_losing,
            )
        )

    return performances


def generate_report_card(
    performances: list[SignalPerformance],
    month: str = "",
) -> str:
    """Generate a plain-text signal performance report card.

    Args:
        performances: List of SignalPerformance records.
        month: Optional label (e.g. "2024-01") included in the header.

    Returns:
        A formatted plain-text report as a single string.
    """
    if not performances:
        return "No signal performance data available for this period."

    header = "Signal Performance Report"
    if month:
        header += f" — {month}"

    sorted_by_hit = sorted(performances, key=lambda p: p.hit_rate, reverse=True)
    sorted_by_return = sorted(
        performances, key=lambda p: p.avg_return_pct, reverse=True
    )

    best = sorted_by_hit[0]
    worst = sorted_by_hit[-1]
    most_profitable = sorted_by_return[0]

    strong = [p for p in performances if p.hit_rate > 50.0]
    weak = [p for p in performances if p.hit_rate <= 50.0]

    lines: list[str] = [
        header,
        "=" * len(header),
        "",
        f"Best signal:      {best.signal_name} ({best.hit_rate:.1f}% hit rate, "
        f"{best.avg_return_pct:.2f}% avg return)",
        f"Worst signal:     {worst.signal_name} ({worst.hit_rate:.1f}% hit rate, "
        f"{worst.avg_return_pct:.2f}% avg return)",
        f"Most profitable:  {most_profitable.signal_name} "
        f"({most_profitable.avg_return_pct:.2f}% avg return)",
        "",
    ]

    if strong:
        lines.append("Strong performers:")
        for p in strong:
            lines.append(
                f"  + {p.signal_name}: {p.hit_rate:.1f}% hit rate, "
                f"{p.avg_return_pct:.2f}% avg return"
            )
        lines.append("")

    if weak:
        lines.append("Consider reducing weight for:")
        for p in weak:
            lines.append(
                f"  - {p.signal_name}: {p.hit_rate:.1f}% hit rate, "
                f"{p.avg_return_pct:.2f}% avg return"
            )
        lines.append("")

    lines.append("Recommendations:")
    if weak:
        for p in weak:
            lines.append(
                f"  * Review or down-weight '{p.signal_name}' — below 50% hit rate."
            )
    else:
        lines.append(
            "  * All signals performing above 50% hit rate. Maintain current weights."
        )

    return "\n".join(lines)
