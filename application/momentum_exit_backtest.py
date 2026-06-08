"""Pre-registered momentum + trend-filter + Chandelier-exit backtest.
Validation gate per spec 2026-06-07. Long-only, monthly rebalance, equal weight."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Callable

from application.evaluation import TransactionCostModel
from domain.backtest_metrics import cagr, daily_returns, max_drawdown, sharpe, sortino
from domain.trend_rules import (
    above_trend,
    atr,
    chandelier_stop,
    momentum_12_1,
    sma,
    top_fraction_threshold,
)

PriceProvider = Callable[[str], list[tuple[datetime, float]]]


class MomentumExitBacktestUseCase:
    def __init__(
        self,
        price_provider: PriceProvider,
        trend_window: int = 200,
        atr_window: int = 22,
        atr_mult: float = 3.0,
        mom_fraction: float = 1.0 / 3.0,
        cost_per_trade: float = 0.001,
    ) -> None:
        self._prices = price_provider
        self._trend_window = trend_window
        self._atr_window = atr_window
        self._atr_mult = atr_mult
        self._mom_fraction = mom_fraction
        self._cost = TransactionCostModel(cost_per_trade=cost_per_trade)

    def _metrics(self, equity: list[float]) -> dict[str, Any]:
        rets = daily_returns(equity)
        return {
            "equity": equity,
            "cagr": cagr(equity),
            "sharpe": sharpe(rets),
            "sortino": sortino(rets),
            "max_drawdown": max_drawdown(equity),
        }

    def execute(
        self, universe: list[str], start: datetime, end: datetime
    ) -> dict[str, Any]:
        # ── 1. Load per-ticker daily closes within [start, end] ──────────────
        # date_closes[ticker][date] = close
        date_closes: dict[str, dict[datetime, float]] = {}
        for ticker in universe:
            raw = self._prices(ticker)
            filtered = {d: c for d, c in raw if start <= d <= end}
            if filtered:
                date_closes[ticker] = filtered

        if not date_closes:
            empty: list[float] = [1.0]
            return {
                "strategy": self._metrics(empty),
                "buy_hold": self._metrics(empty),
                "universe": universe,
            }

        # ── 2. Shared trading-day calendar ───────────────────────────────────
        all_dates: list[datetime] = sorted(
            {d for closes in date_closes.values() for d in closes}
        )

        # ── 3. Per-ticker running state ──────────────────────────────────────
        # closes_so_far: point-in-time list of closes (no look-ahead)
        closes_so_far: dict[str, list[float]] = {t: [] for t in date_closes}
        # month_end_closes: last close seen for each completed month
        month_end_closes: dict[str, list[float]] = {t: [] for t in date_closes}
        last_month: dict[str, tuple[int, int]] = {}  # (year, month) last appended

        # Strategy state per ticker
        # held[ticker] = True means currently held (positions decided at END of prior day)
        held: dict[str, bool] = {t: False for t in date_closes}
        entry_closes: dict[str, list[float]] = {
            t: [] for t in date_closes
        }  # closes since entry

        # prev_held: snapshot of the held set from end of prior day (for turnover calc)
        prev_held: dict[str, bool] = {t: False for t in date_closes}

        # ── equity curves ────────────────────────────────────────────────────
        strat_eq: list[float] = [1.0]
        bh_eq: list[float] = [1.0]

        prev_date: datetime | None = None

        for i, today in enumerate(all_dates):
            # Determine if this is the first trading day of a new month
            is_new_month = False
            if prev_date is None:
                is_new_month = True
            elif (today.year, today.month) != (prev_date.year, prev_date.month):
                is_new_month = True

            # ── STEP 1: Append close[today] to closes_so_far ─────────────────
            for ticker, dc in date_closes.items():
                if today in dc:
                    closes_so_far[ticker].append(dc[today])

            # ── STEP 2: Book daily return using PRIOR-DAY held state ─────────
            # The positions in `held`/`entry_closes` were decided at the end of
            # day t-1. We pay today's move before making any new decisions.
            if i > 0:
                # Strategy return: mean of held names' daily returns
                strat_rets: list[float] = []
                for ticker, dc in date_closes.items():
                    if not held[ticker]:
                        continue
                    c = closes_so_far[ticker]
                    if len(c) < 2:
                        continue
                    ret = (c[-1] - c[-2]) / c[-2] if c[-2] != 0 else 0.0
                    strat_rets.append(ret)
                strat_ret = sum(strat_rets) / len(strat_rets) if strat_rets else 0.0

                # Compute one-way turnover entering today:
                # turnover = 0.5 * sum_over_names |w_t(name) - w_{t-1}(name)|
                # where w = 1/|held_set| for held names, else 0.
                # held and prev_held reflect the decisions made at end of t-1 and
                # t-2 respectively — both known before today's open. No look-ahead.
                n_held_today = sum(1 for t in date_closes if held[t])
                n_held_prev = sum(1 for t in date_closes if prev_held[t])
                w_today = 1.0 / n_held_today if n_held_today > 0 else 0.0
                w_prev = 1.0 / n_held_prev if n_held_prev > 0 else 0.0
                turnover = 0.5 * sum(
                    abs(
                        (w_today if held[t] else 0.0)
                        - (w_prev if prev_held[t] else 0.0)
                    )
                    for t in date_closes
                )
                cost_today = self._cost.cost_for_turnover(turnover)
                strat_ret = strat_ret - cost_today

                strat_eq.append(strat_eq[-1] * (1.0 + strat_ret))

                # Buy-hold return: mean of all names' daily returns (if data available)
                bh_rets: list[float] = []
                for ticker, dc in date_closes.items():
                    c = closes_so_far[ticker]
                    if len(c) < 2:
                        continue
                    ret = (c[-1] - c[-2]) / c[-2] if c[-2] != 0 else 0.0
                    bh_rets.append(ret)
                bh_ret = sum(bh_rets) / len(bh_rets) if bh_rets else 0.0
                bh_eq.append(bh_eq[-1] * (1.0 + bh_ret))

            # ── STEP 3: Update month_end_closes on month boundary ────────────
            # On the first trading day of a new month, the previous month's
            # last close is now fully observed — record it.
            if is_new_month and prev_date is not None:
                for ticker in date_closes:
                    c = closes_so_far[ticker]
                    if c:
                        lm = last_month.get(ticker)
                        prev_ym = (prev_date.year, prev_date.month)
                        if lm != prev_ym:
                            month_end_closes[ticker].append(c[-1])
                            last_month[ticker] = prev_ym

            # ── STEP 4: Monthly rebalance — update held set for tomorrow ─────
            if is_new_month:
                # Compute momentum for all tickers with enough data
                mom_vals: dict[str, float] = {}
                for ticker in date_closes:
                    mc = month_end_closes[ticker]
                    m = momentum_12_1(mc)
                    if m is not None:
                        mom_vals[ticker] = m

                # Compute top-fraction threshold across universe
                threshold = top_fraction_threshold(
                    list(mom_vals.values()), self._mom_fraction
                )

                # Decide new held set (takes effect from tomorrow)
                for ticker in date_closes:
                    c = closes_so_far[ticker]
                    if not c:
                        held[ticker] = False
                        continue

                    close = c[-1]
                    trend_val = sma(c, self._trend_window)
                    in_trend = above_trend(close, trend_val)

                    mom = mom_vals.get(ticker)
                    if mom is not None and threshold is not None:
                        in_top = mom >= threshold
                    else:
                        # Not enough momentum history — still check trend only
                        # but do NOT hold (need at least some signal)
                        in_top = False

                    # When there's only one name (single-name universe) and
                    # threshold is exactly that one name's momentum, in_top=True
                    should_hold = in_trend and in_top

                    if should_hold and not held[ticker]:
                        # Enter: reset entry tracking
                        held[ticker] = True
                        entry_closes[ticker] = list(c)
                    elif not should_hold:
                        held[ticker] = False
                        entry_closes[ticker] = []

            # ── STEP 5: Intra-month Chandelier stop — update held for tomorrow
            # A stop that triggers on today still costs today's move (already
            # booked above). The exit takes effect from tomorrow.
            for ticker in list(date_closes.keys()):
                if not held[ticker]:
                    continue
                c = closes_so_far[ticker]
                if not c:
                    continue
                close = c[-1]
                # Update entry_closes with today's close
                if entry_closes[ticker] and entry_closes[ticker][-1] != close:
                    entry_closes[ticker].append(close)
                ec = entry_closes[ticker]
                highest = max(ec) if ec else close
                atr_val = atr(ec, ec, ec, self._atr_window)
                if atr_val is not None:
                    stop = chandelier_stop(highest, atr_val, self._atr_mult)
                    if close < stop:
                        held[ticker] = False
                        entry_closes[ticker] = []

            # Snapshot held state at end of today (becomes prev_held for tomorrow)
            prev_held = dict(held)

            prev_date = today

        result: dict[str, Any] = {
            "strategy": self._metrics(strat_eq),
            "buy_hold": self._metrics(bh_eq),
            "universe": universe,
        }

        # SPY buy-hold baseline (optional — omitted when provider returns no data)
        spy_raw = self._prices("SPY")
        if spy_raw:
            spy_filtered = [(d, c) for d, c in spy_raw if start <= d <= end]
            if spy_filtered:
                spy_eq: list[float] = [1.0]
                spy_closes = [c for _, c in sorted(spy_filtered)]
                for j in range(1, len(spy_closes)):
                    prev_c = spy_closes[j - 1]
                    ret = (spy_closes[j] - prev_c) / prev_c if prev_c != 0 else 0.0
                    spy_eq.append(spy_eq[-1] * (1.0 + ret))
                result["spy"] = self._metrics(spy_eq)

        return result

    def verdict(
        self, report: dict[str, Any], sharpe_diff_ci_low: float
    ) -> dict[str, Any]:
        strat = report["strategy"]
        bh = report["buy_hold"]
        bh_dd = bh["max_drawdown"]
        dd_reduction = (bh_dd - strat["max_drawdown"]) / bh_dd if bh_dd > 0 else 0.0
        beats_sharpe = sharpe_diff_ci_low > 0.0  # bootstrap CI excludes 0, positive
        cuts_drawdown = dd_reduction >= 0.30
        decision = "PROCEED" if (beats_sharpe and cuts_drawdown) else "KILL"
        return {
            "decision": decision,
            "sharpe_diff_ci_low": sharpe_diff_ci_low,
            "drawdown_reduction": dd_reduction,
            "beats_sharpe": beats_sharpe,
            "cuts_drawdown": cuts_drawdown,
        }
