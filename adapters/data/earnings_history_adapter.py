"""Net-new yfinance earnings-surprise fetcher. Revenue surprise NOT fetched (stays DATA-GAP)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import pandas as pd


@dataclass(frozen=True)
class EpsQuarter:
    label: str
    eps_actual: float | None
    eps_estimate: float | None
    surprise_pct: float | None


@dataclass(frozen=True)
class EarningsHistory:
    quarters: tuple[EpsQuarter, ...]
    beats: int
    total: int


def parse_earnings_frame(df: pd.DataFrame | None) -> EarningsHistory | None:
    if df is None or len(df) == 0 or "Reported EPS" not in df.columns:
        return None
    reported = df[df["Reported EPS"].notna()].sort_index(ascending=False).head(4)
    if len(reported) == 0:
        return None
    quarters: list[EpsQuarter] = []
    beats = 0
    for idx, row in reported.iterrows():
        surprise = row.get("Surprise(%)")
        s = float(surprise) if surprise is not None and not pd.isna(surprise) else None
        if s is not None and s > 0:
            beats += 1
        quarters.append(
            EpsQuarter(
                label=pd.Timestamp(str(idx)).strftime("%b"),
                eps_actual=_f(row.get("Reported EPS")),
                eps_estimate=_f(row.get("EPS Estimate")),
                surprise_pct=s,
            )
        )
    return EarningsHistory(quarters=tuple(quarters), beats=beats, total=len(quarters))


def _f(v: Any) -> float | None:
    return None if v is None or pd.isna(v) else float(v)


def _fetch_earnings_history_impl(ticker: str) -> EarningsHistory | None:
    import yfinance as yf  # lazy import for CI safety

    try:
        df = yf.Ticker(
            ticker
        ).earnings_dates  # verified: returns DataFrame with EPS columns
    except Exception:  # noqa: BLE001 — network/parse failures → honest None (DATA-GAP)
        return None
    return parse_earnings_frame(df)


def fetch_earnings_history(ticker: str) -> EarningsHistory | None:
    """Streamlit-cached wrapper added in S5; for now a thin pass-through."""
    return _fetch_earnings_history_impl(ticker)
