"""Assess currently-held positions: graded discipline verdict per holding +
book-level risk. Decision-support, not prediction (spec 2026-06-08)."""

from __future__ import annotations

import statistics
from datetime import datetime
from typing import Any, Callable, Protocol

from application.holdings_reader import Holding
from application.narrator import template_narration
from domain.backtest_metrics import daily_returns
from domain.discipline import (
    Verdict,
    conditional_vol_signal,
    grade_position,
    is_disposition_risk,
    is_winner_past_stop,
    risk_asymmetry,
)
from domain.models import PortfolioRisk, PositionRisk
from domain.trend_rules import (
    atr,
    chandelier_stop,
    relative_strength,
    sma,
    trend_health,
)

PriceProvider = Callable[[str], list[tuple[datetime, float]]]

_TREND_WINDOW = 200
_ATR_WINDOW = 22
_ATR_MULT = 3.0
_RECENT_VOL = 22
_BASE_VOL = 252
_RS_WINDOW = 126


class _Narrator(Protocol):
    def narrate(self, context: dict[str, object]) -> str: ...


class HoldingsRiskAssessmentUseCase:
    def __init__(
        self, price_provider: PriceProvider, narrator: _Narrator, benchmark: str = "SPY"
    ) -> None:
        self._prices = price_provider
        self._narrator = narrator
        self._benchmark = benchmark

    def _closes_in(self, ticker: str, start: datetime, end: datetime) -> list[float]:
        # Normalize to naive UTC: live price providers (yfinance) return tz-naive
        # datetimes while callers pass tz-aware bounds; comparing the two raises.
        s = start.replace(tzinfo=None)
        e = end.replace(tzinfo=None)
        return [c for d, c in self._prices(ticker) if s <= d.replace(tzinfo=None) <= e]

    def _vol(self, returns: list[float], window: int) -> float:
        tail = [float(x) for x in returns[-window:]]
        return statistics.pstdev(tail) if len(tail) >= 2 else 0.0

    def execute(
        self, holdings: list[Holding], start: datetime, end: datetime
    ) -> dict[str, Any]:
        bench_closes = self._closes_in(self._benchmark, start, end)
        market_th: float | None = None
        if len(bench_closes) >= _TREND_WINDOW:
            market_th = trend_health(
                bench_closes[-1],
                sma(bench_closes, _TREND_WINDOW),
                atr(bench_closes, bench_closes, bench_closes, _ATR_WINDOW),
            )

        fx_series = self._prices("USDCAD=X")
        usdcad: float | None = fx_series[-1][1] if fx_series else None

        positions: list[PositionRisk] = []
        for h in holdings:
            closes = self._closes_in(h.ticker, start, end)
            if len(closes) < _TREND_WINDOW:
                positions.append(self._insufficient(h))
                continue
            price = closes[-1]
            th = trend_health(
                price,
                sma(closes, _TREND_WINDOW),
                atr(closes, closes, closes, _ATR_WINDOW),
            )
            atr_v = atr(closes, closes, closes, _ATR_WINDOW)
            highest = max(closes[-_TREND_WINDOW:])
            stop = chandelier_stop(highest, atr_v, _ATR_MULT) if atr_v else None
            rets = daily_returns(closes)
            vol_sig = conditional_vol_signal(
                self._vol(rets, _RECENT_VOL), self._vol(rets, _BASE_VOL), th
            )
            rs = (
                relative_strength(closes, bench_closes, _RS_WINDOW)
                if bench_closes
                else None
            )
            unreal = (
                (price * h.shares - h.cost_basis) / h.cost_basis
                if h.cost_basis > 0
                else 0.0
            )
            disp = is_disposition_risk(th, unreal)
            wps = is_winner_past_stop(th, price, stop)
            verdict, conf, abstained = grade_position(
                th, vol_sig, rs, disp, wps, market_th
            )
            asym = risk_asymmetry(price, stop, highest)
            flags = tuple(
                f
                for f, on in (("disposition_risk", disp), ("winner_past_stop", wps))
                if on
            )
            ctx: dict[str, object] = {
                "ticker": h.ticker,
                "verdict": verdict.value,
                "trend_health": th,
                "unrealized_pct": unreal,
                "account_type": h.account_type,
                "downside_to_stop": asym["downside_to_stop"],
                "upside_to_recover": asym["upside_to_recover"],
                "behavior_flags": list(flags),
            }
            why = self._narrator.narrate(ctx) or template_narration(ctx)
            positions.append(
                PositionRisk(
                    ticker=h.ticker,
                    price=price,
                    verdict=verdict,
                    confidence=conf,
                    trend_health=th,
                    vol_signal=vol_sig,
                    relative_strength=rs,
                    downside_to_stop=asym["downside_to_stop"],
                    upside_to_recover=asym["upside_to_recover"],
                    behavior_flags=flags,
                    unrealized_pct=unreal,
                    account_type=h.account_type,
                    abstained=abstained,
                    why=why,
                    quantity=h.shares,
                    market_value_cad=self._market_value_cad(
                        h.ticker, price, h.shares, usdcad
                    ),
                )
            )
        return {"positions": positions, "portfolio": self._portfolio(positions)}

    def _insufficient(self, h: Holding) -> PositionRisk:
        return PositionRisk(
            ticker=h.ticker,
            price=0.0,
            verdict=Verdict.REVIEW,
            confidence=0.1,
            trend_health=None,
            vol_signal=0.0,
            relative_strength=None,
            downside_to_stop=0.0,
            upside_to_recover=0.0,
            behavior_flags=(),
            unrealized_pct=0.0,
            account_type=h.account_type,
            abstained=True,
            why=f"{h.ticker}: not enough price history to assess.",
            quantity=h.shares,
            market_value_cad=None,
        )

    def _market_value_cad(
        self, ticker: str, price: float, shares: float, usdcad: float | None
    ) -> float | None:
        """CAD market value via suffix-inferred currency (mirrors
        holdings_reader._to_yf): .TO/.V are CAD-native, everything else USD.
        Missing FX -> None (never silently native currency — spec v4)."""
        if ticker.endswith((".TO", ".V")):
            return price * shares
        if usdcad is None:
            return None
        return price * shares * usdcad

    def _portfolio(self, positions: list[PositionRisk]) -> PortfolioRisk:
        n = len(positions)
        if n == 0:
            return PortfolioRisk(0, 0.0, 0.0, {})
        broken = sum(
            1 for p in positions if p.trend_health is not None and p.trend_health < 0
        )
        counts: dict[str, int] = {}
        for p in positions:
            counts[p.verdict.value] = counts.get(p.verdict.value, 0) + 1
        values = [
            p.market_value_cad
            for p in positions
            if p.market_value_cad is not None and p.market_value_cad > 0
        ]
        top = (max(values) / sum(values)) if values else 0.0
        return PortfolioRisk(
            n_positions=n,
            broken_trend_share=broken / n,
            top_concentration=top,
            verdict_counts=counts,
        )
