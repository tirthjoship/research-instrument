"""Ticker factor lookup / live-compute use case (S5 Task 2).

Given a ticker and a persisted screen, returns 5 factor score dicts
(name, value, percentile, source) suitable for rendering the Zone ② card.

- In-screen path: returns stored factor_scores directly (free, zero computation).
- Off-universe path: calls fetch_fn for raw z-scores, ranks them against the
  cohort z-distribution reconstructed from all candidates in the screen —
  mirroring evidence_screen_use_case.py:119-141 (no new scoring logic).
- DATA-GAP: if fetch_fn raises or returns None for a factor, the row is
  {"name": f, "value": None, "percentile": None, "source": "live"}.

Design: fetch_fn is an injected Callable[str, dict[str, float|None]] so tests
can supply a fake without touching any live adapter.

live_factor_fetch_fn() builds a real fetch callable using the same adapters
as the evidence_screen_use_case (YFinanceAdapter). For off-universe tickers
pasted into Zone ②, it computes:
  - momentum   via domain.trend_rules.momentum_12_1 on monthly closes
  - lowvol     via -domain.trend_rules.trailing_volatility on daily closes
               (inverted: calmer = higher z; DATA-GAP when < 61 closes)
  - revision   via domain.factor_scores.revision_momentum on analyst targets
  - quality    from yfinance return_on_equity / profit_margins
  - value      as 1/trailing_pe (DATA-GAP when trailing_pe is None/non-positive)
All None → DATA-GAP; no values are fabricated. PIT-safe (as_of = now()).
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Callable

_ALL_FACTORS: tuple[str, ...] = ("momentum", "revision", "quality", "value", "lowvol")


def _rank_vs_cohort(z: float, cohort_zs: list[float]) -> float:
    """Rank *z* among *cohort_zs*; return 0-indexed fraction in [0, 1]."""
    n = len(cohort_zs)
    if n == 0:
        return 0.0
    beaten = sum(1 for cz in cohort_zs if cz < z)
    return beaten / max(n - 1, 1)


def ticker_factor_scores(
    ticker: str,
    screen: dict[str, Any],
    fetch_fn: Callable[[str], dict[str, float | None]],
) -> list[dict[str, Any]]:
    """Return 5 factor score dicts for *ticker*.

    Each dict has keys: name, value, percentile, source.

    Args:
        ticker: Stock ticker to look up or compute.
        screen: Persisted screen dict (with "candidates" list of dicts).
        fetch_fn: Callable that accepts a ticker and returns a dict of
            factor_name -> raw z-score (or None for DATA-GAP). Only called
            for off-universe tickers.

    Returns:
        List of 5 dicts, one per factor in _ALL_FACTORS order.
    """
    candidates: list[dict[str, Any]] = screen.get("candidates", [])

    # --- In-screen path: reuse stored scores ---
    for cand in candidates:
        if cand.get("ticker") == ticker:
            stored: list[dict[str, Any]] = list(cand.get("factor_scores", []))
            # Ensure all 5 factors are represented (backfill any missing as DATA-GAP)
            result: list[dict[str, Any]] = []
            for fname in _ALL_FACTORS:
                match = next((f for f in stored if f.get("name") == fname), None)
                if match is not None:
                    result.append(
                        {
                            "name": fname,
                            "value": match.get("value"),
                            "percentile": match.get("percentile"),
                            "source": "screen",
                        }
                    )
                else:
                    result.append(
                        {
                            "name": fname,
                            "value": None,
                            "percentile": None,
                            "source": "screen",
                        }
                    )
            return result

    # --- Off-universe path: fetch raw z-scores, rank vs cohort ---
    # Build cohort z-distribution from all stored candidates (per factor)
    cohort_zs: dict[str, list[float]] = {f: [] for f in _ALL_FACTORS}
    for cand in candidates:
        for fs in cand.get("factor_scores", []):
            fname = fs.get("name")
            val = fs.get("value")
            if fname in cohort_zs and val is not None:
                cohort_zs[fname].append(float(val))

    # Attempt live fetch
    try:
        raw = fetch_fn(ticker)
    except Exception:
        # DATA-GAP: fetch failed entirely
        return [
            {"name": f, "value": None, "percentile": None, "source": "live"}
            for f in _ALL_FACTORS
        ]

    # Rank each factor's raw z against the cohort
    live_result: list[dict[str, Any]] = []
    for fname in _ALL_FACTORS:
        z = raw.get(fname) if raw else None
        if z is None:
            live_result.append(
                {"name": fname, "value": None, "percentile": None, "source": "live"}
            )
        else:
            pct = _rank_vs_cohort(float(z), cohort_zs.get(fname, []))
            live_result.append(
                {
                    "name": fname,
                    "value": float(z),
                    "percentile": pct,
                    "source": "live",
                }
            )
    return live_result


# ---------------------------------------------------------------------------
# Live fetch factory — mirrors _PriceAdapter / _AnalystAdapter / _FundamentalsAdapter
# in application/cli.py _build_evidence_screen, but at module level so Zone ②
# can call it without importing the full CLI context.
# ---------------------------------------------------------------------------


def live_factor_fetch_fn() -> Callable[[str], dict[str, float | None]]:
    """Return a callable fetch(ticker) -> dict[factor, raw_z | None].

    Raw sub-scores mirror the screen's computation:
      - momentum  : domain.trend_rules.momentum_12_1(monthly_closes)
      - lowvol    : -domain.trend_rules.trailing_volatility(daily_closes)
                    (inverted so calmer → higher; None when < 61 daily closes)
      - revision  : domain.factor_scores.revision_momentum(estimate_series)
      - quality   : return_on_equity or profit_margins from yfinance
      - value     : 1/trailing_pe (None when missing or non-positive)

    Any missing input produces None (DATA-GAP) — never fabricated.
    PIT-safe: uses datetime.now(UTC) as as_of for all fetches.

    The returned callable is safe to inject into ticker_factor_scores as fetch_fn.
    """
    from pathlib import Path

    from adapters.data.yfinance_adapter import YFinanceAdapter
    from domain.factor_scores import revision_momentum
    from domain.trend_rules import momentum_12_1, trailing_volatility

    # Use a temporary cache dir (or no-cache) — same pattern as CLI's adapter init
    _adapter = YFinanceAdapter(cache_dir=Path("data/cache"), use_cache=False)

    def _fetch(ticker: str) -> dict[str, float | None]:
        now = datetime.now(timezone.utc)
        two_years_ago = now.replace(year=now.year - 2)

        # --- momentum (12-1 month) via monthly closes ---
        mom: float | None = None
        try:
            signals = _adapter.get_signals(ticker, now, start_date=two_years_ago)
            if signals:
                by_month: dict[str, float] = {}
                for s in signals:
                    key = f"{s.timestamp.year}-{s.timestamp.month:02d}"
                    by_month[key] = s.price
                monthly_closes = [by_month[k] for k in sorted(by_month)]
                mom = momentum_12_1(monthly_closes)
        except Exception:
            mom = None

        # --- lowvol (inverted trailing volatility) via daily closes ---
        lowvol: float | None = None
        try:
            daily_signals = _adapter.get_signals(ticker, now, start_date=two_years_ago)
            if daily_signals:
                daily_closes = [s.price for s in daily_signals]
                vol = trailing_volatility(daily_closes)
                lowvol = -vol if vol is not None else None
        except Exception:
            lowvol = None

        # --- revision (analyst target-price spread) ---
        rev: float | None = None
        try:
            data = _adapter.get_analyst_data(ticker, now)
            if data is not None:
                targets = [
                    v
                    for k, v in data.items()
                    if "target" in k and isinstance(v, (int, float))
                ]
                rev = revision_momentum(targets if targets else None)
        except Exception:
            rev = None

        # --- quality & value from fundamentals ---
        quality: float | None = None
        value: float | None = None
        try:
            info = _adapter.get_ticker_info(ticker)
            q = info.get("return_on_equity") or info.get("profit_margins")
            quality = float(q) if q is not None else None
            pe = info.get("trailing_pe")
            value = (1.0 / float(pe)) if pe and float(pe) > 0 else None
        except Exception:
            quality = None
            value = None

        return {
            "momentum": mom,
            "revision": rev,
            "quality": quality,
            "value": value,
            "lowvol": lowvol,
        }

    return _fetch
