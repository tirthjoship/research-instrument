"""Streamlit-cached card fetches + the lazy-case gate.

Cache-first strategy (D2):
  1. If collapsed → return None immediately (no work).
  2. If expanded → check weekly cited-case cache (data/personal/cited_cases.json).
     Cache hit → return cached CaseResult, zero live pings.
     Cache miss → call summarizer.summarize_case (live Gemini ping, throttled).

Public helpers (shared with portfolio tab and weekly_brief):
  - fetch_card(ticker) — real EvidenceCard or GAP fallback
  - implied_cost(price, unrealized_pct) — back-calculate cost basis
  - window_returns(closes) — windowed % returns from daily closes
"""

from __future__ import annotations

from typing import Any

from application.case_builder import build_case_context
from application.case_cache import CITED_CASES_PATH, load_cached_case
from application.evidence_card import EvidenceCard
from domain.case_models import CaseResult
from domain.evidence_rag import DIMENSIONS, RagColor, RagSignal

# Module-level path constant — monkeypatchable in tests.
_CITED_CASES_PATH: str = CITED_CASES_PATH

_WINDOW_DAYS = (7, 30, 90, 180, 252)


# ---------------------------------------------------------------------------
# Shared pure helpers — price / cost / windowed returns
# ---------------------------------------------------------------------------


def implied_cost(price: float | None, unrealized_pct: float | None) -> float | None:
    """Back-calculate cost basis from price and unrealized %.

    Formula: cost = price / (1 + unrealized_pct / 100)

    Returns None when either input is None so the card shows "—" honestly.

    Examples:
        implied_cost(44.63, 22.7) → ~36.37
        implied_cost(100.0, 0.0) → 100.0
        implied_cost(None, 22.7) → None
        implied_cost(100.0, None) → None
    """
    if price is None or unrealized_pct is None:
        return None
    divisor = 1.0 + unrealized_pct / 100.0
    if divisor == 0.0:
        return None
    return price / divisor


def window_returns(
    closes: list[float],
    windows: tuple[int, ...] = _WINDOW_DAYS,
) -> tuple[float, ...]:
    """Compute % change for each look-back window from a list of daily closes.

    For each window W in ``windows``, returns ``(closes[-1] / closes[-1-W] - 1) * 100``
    when there are enough data points (at least W+1 closes), otherwise skips that window.

    Returns a tuple of available returns (may be shorter than ``windows``).
    Empty closes → empty tuple.

    Examples:
        window_returns([], (7, 30)) → ()
        window_returns(closes_200, (7, 30, 90, 180)) → 4-tuple of floats
    """
    if not closes:
        return ()
    last = closes[-1]
    results: list[float] = []
    for w in windows:
        if len(closes) >= w + 1:
            base = closes[-1 - w]
            if base != 0.0:
                results.append((last / base - 1.0) * 100.0)
    return tuple(results)


# ---------------------------------------------------------------------------
# Shared card builders
# ---------------------------------------------------------------------------


def _home_evidence_card(ticker: str) -> EvidenceCard:
    """Minimal GAP card — used as fallback when fetch fails or data is unavailable."""
    sigs = tuple(
        RagSignal(d, RagColor.GAP, "DATA-GAP: loads on open") for d in DIMENSIONS
    )
    return EvidenceCard(ticker=ticker, signals=sigs, sparkline=())


def fetch_card(ticker: str) -> EvidenceCard:
    """Fetch a real EvidenceCard for a ticker via cached adapters (S5).

    On any fetch failure (network, bare-mode CI) falls back to the GAP card
    so the UI remains honest rather than crashing.
    """
    try:
        from adapters.data.earnings_history_adapter import fetch_earnings_history
        from adapters.visualization.price_cache import (
            fetch_price_history,
            fetch_prices,
            fetch_ticker_info,
        )
        from application.analyst_panel import build_analyst_panel
        from application.evidence_card import build_evidence_card

        raw = fetch_ticker_info(ticker)
        info: dict[str, Any] = {k: v for k, v in raw.items()}
        px = fetch_prices((ticker,)).get(ticker, {})
        info["current_price"] = px.get("price")
        # snake_case keys S1 expects
        info["trailing_pe"] = raw.get("trailingPE")
        info["peg_ratio"] = raw.get("pegRatio")
        info["free_cashflow"] = raw.get("freeCashflow")
        info["debt_to_equity"] = raw.get("debtToEquity")
        # Remap yfinance raw keys → build_analyst_panel's expected keys (mirror stock_analyzer)
        panel_info: dict[str, Any] = dict(raw)
        panel_info["analyst_count"] = raw.get("numberOfAnalystOpinions", 0)
        panel_info["analyst_recommendation_mean"] = raw.get("recommendationMean")
        # target keys are already camelCase and match build_analyst_panel directly:
        # targetMeanPrice, targetHighPrice, targetLowPrice — no remap needed
        panel = build_analyst_panel(panel_info, "")
        # Fetch 1-year price history for closes/ATR/MA200 (lights Technicals + sparkline)
        hist = fetch_price_history(ticker) or {}
        prices: dict[str, Any] = {
            "closes": hist.get("closes", []),
            "atr": hist.get("atr"),
            "ma200": hist.get("ma200"),
            "spy_1y": None,  # DATA-GAP: not tracked per holding on Home
            "book_1y": None,  # DATA-GAP: not tracked per holding on Home
        }
        peers: list[float | None] = []  # DATA-GAP: peer data not fetched on Home
        return build_evidence_card(
            ticker,
            info=info,
            prices=prices,
            panel=panel,
            earnings=fetch_earnings_history(ticker),
            peers=peers,
        )
    except Exception:  # noqa: BLE001 — network/CI failures → GAP card (honest)
        return _home_evidence_card(ticker)


def get_case_on_expand(
    ticker: str,
    card: EvidenceCard,
    news: list[object],
    *,
    expanded: bool,
    summarizer: object,
) -> CaseResult | None:
    """Fetch the cited case ONLY when the card is expanded. Returns None when collapsed.

    Cache-first: checks the weekly cited-case cache before making a live Gemini
    ping.  A cache hit returns immediately with zero network calls.  Only on a
    miss is summarizer.summarize_case(...) invoked (the throttled live path).
    """
    if not expanded:
        return None

    # Cache-first: weekly prefetch wins over live ping.
    cached = load_cached_case(_CITED_CASES_PATH, ticker)
    if cached is not None:
        return cached

    # Cache miss — live ping (rate-limited by the summarizer itself).
    sigs = tuple(s for s in card.signals if s.color is not RagColor.GAP)
    ctx = build_case_context(ticker, sigs, news)  # type: ignore[arg-type]
    result: CaseResult = summarizer.summarize_case(ctx)  # type: ignore[attr-defined]
    return result
